"""Immutable edits, branch-visible versions and frozen context with fake providers."""
from uuid import uuid4

import pytest
import sqlalchemy as sa
from pydantic import ValidationError

from izo.chat import tables as t
from izo.chat.branches import branch_page, change_branch
from izo.chat.graph_requests import admit_request
from izo.chat.graph_schemas import BranchEdit, BranchSelection
from izo.chat.history_pages import attempt_page, graph_page
from izo.chat.schemas import RequestCreate
from izo.chat.service import ChatError
from test_chat import chat_env, connect_key, new_thread, request
from test_chat_graph_context import finish
from test_chat_graph_requests import prepare, regenerate, select


def edit_command(service, owner, thread_id, text, turn_id=None):
    page = graph_page(service, owner.bearer, thread_id)
    turn = page.turns[-1] if turn_id is None else attempt_page(service, owner.bearer, thread_id, turn_id).turn
    source = turn.selected_attempt or turn.latest_attempt
    return turn.id, BranchEdit(request_id=uuid4(), branch_id=page.active_branch_id,
        source_attempt_id=source.id, expected_revision=page.revision, text=text)


def edit(service, owner, thread_id, text, turn_id=None):
    source_id, command = edit_command(service, owner, thread_id, text, turn_id)
    return admit_request(service, owner.bearer, owner.view.csrf_token,
        thread_id, command, source_id, edit=True), command, source_id


def switch(service, owner, thread_id, target):
    page = graph_page(service, owner.bearer, thread_id)
    return change_branch(service, owner.bearer, owner.view.csrf_token, thread_id,
        BranchSelection(branch_id=page.active_branch_id, target_branch_id=target,
            expected_revision=page.revision))


def send(service, owner, thread_id, text):
    page = graph_page(service, owner.bearer, thread_id)
    return service.create_request(owner.bearer, owner.view.csrf_token, thread_id,
        RequestCreate(request_id=uuid4(), text=text, model="deepseek-flash",
            branch_id=page.active_branch_id, expected_revision=page.revision))


def durable_rows(service):
    with service.engine.begin() as conn:
        return {table.name: [dict(row) for row in conn.execute(sa.select(table)
            .order_by(*table.primary_key.columns)).mappings()] for table in t.TABLES}


def test_edit_preserves_original_history_title_and_only_selected_prefix_context(chat_env):
    service, alice, _, _ = chat_env
    thread, first, provider = prepare(service, alice)
    service.rename_thread(alice.bearer, alice.view.csrf_token, thread.id, "Моё название")
    middle = request(service, alice, thread.id, "Старый средний вопрос")
    finish(service, alice, middle)
    later = request(service, alice, thread.id, "Старый suffix")
    finish(service, alice, later)
    original = service.thread_detail(alice.bearer, thread.id)
    root = graph_page(service, alice.bearer, thread.id)
    before = durable_rows(service)
    accepted, _, source_id = edit(service, alice, thread.id, "Новый вопрос", root.turns[1].id)
    assert accepted.created_branch.parent_branch_id == thread.id
    assert accepted.created_branch.fork_from_turn_id == source_id
    assert accepted.created_branch.branch_ordinal == 2
    assert accepted.active_branch_id == accepted.created_branch.id != thread.id
    child = graph_page(service, alice.bearer, thread.id)
    assert [turn.id for turn in child.turns] == [root.turns[0].id, accepted.turn_id]
    assert child.turns[-1].selected_attempt is None and child.turns[-1].latest_attempt.state == "pending"
    assert service.thread_detail(alice.bearer, thread.id).messages[:6] == original.messages
    assert service.thread_detail(alice.bearer, thread.id).thread.title == "Моё название"
    assert len(provider.calls) == 3
    finish(service, alice, accepted.request)
    assert [message["content"] for message in provider.calls[-1][1:]] == [
        "Исходный вопрос", "Вариант 1: сохранённый ответ", "Новый вопрос"]
    with service.engine.begin() as conn:
        old = conn.execute(sa.select(t.contexts).where(t.contexts.c.request_id.in_([first.id, middle.id, later.id]))).mappings().all()
        assert sorted([dict(row) for row in old], key=lambda row: row["request_id"]) == before[t.contexts.name]
        context = conn.execute(sa.select(t.contexts).where(t.contexts.c.request_id == accepted.request.id)).mappings().one()
        assert context["kind"] == "edit" and context["branch_id"] == accepted.created_branch.id
    restored = switch(service, alice, thread.id, thread.id)
    assert restored.turns == root.turns
    with pytest.raises(ChatError, match="branch_selection_required"):
        request(service, alice, thread.id, "Unfenced new send")
    assert request(service, alice, thread.id, "Исходный вопрос", request_id=first.id).id == first.id
    continued = send(service, alice, thread.id, "Продолжение parent")
    finish(service, alice, continued)
    assert provider.calls[-1][-2]["content"] == "Вариант 3: сохранённый ответ"


def test_inherited_manual_selection_and_execution_are_branch_local(chat_env):
    service, alice, _, _ = chat_env
    thread, first, _ = prepare(service, alice)
    second, _ = regenerate(service, alice, thread.id)
    finish(service, alice, second.request)
    select(service, alice, thread.id, second.turn.id, first.id)
    suffix = request(service, alice, thread.id, "Fork here")
    finish(service, alice, suffix)
    child, _, _ = edit(service, alice, thread.id, "Child fork")
    finish(service, alice, child.request)
    switch(service, alice, thread.id, thread.id)
    parent_late, _ = regenerate(service, alice, thread.id, second.turn.id)
    finish(service, alice, parent_late.request)
    switch(service, alice, thread.id, child.created_branch.id)
    visible = attempt_page(service, alice.bearer, thread.id, second.turn.id)
    assert [attempt.id for attempt in visible.attempts] == [first.id, second.request.id]
    assert visible.turn.completed_count == 2
    chosen = select(service, alice, thread.id, second.turn.id, second.request.id)
    assert chosen.turn.selected_attempt_id == second.request.id
    child_late, _ = regenerate(service, alice, thread.id, second.turn.id)
    finish(service, alice, child_late.request)
    with service.engine.begin() as conn:
        attempt = conn.execute(sa.select(t.attempts).where(t.attempts.c.id == child_late.request.id)).mappings().one()
        origin = conn.execute(sa.select(t.turns).where(t.turns.c.id == second.turn.id)).mappings().one()
        assert origin["branch_id"] == thread.id and attempt["branch_id"] == child.created_branch.id
        assert attempt["ordinal"] == 4
        assert conn.execute(sa.select(t.contexts.c.branch_id).where(
            t.contexts.c.request_id == child_late.request.id)).scalar_one() == child.created_branch.id
    switch(service, alice, thread.id, thread.id)
    parent = attempt_page(service, alice.bearer, thread.id, second.turn.id)
    assert parent.turn.selected_attempt_id == parent_late.request.id
    assert [attempt.ordinal for attempt in parent.attempts] == [1, 2, 3]
    assert service._finish(child_late.request.id, "completed", None, "late overwrite") == "completed"
    assert graph_page(service, alice.bearer, thread.id).turns[0].selected_attempt_id == parent_late.request.id


def test_exact_edit_replay_never_readmits_or_reactivates_and_revision_is_not_material(chat_env, monkeypatch):
    service, alice, _, _ = chat_env
    thread, _, provider = prepare(service, alice)
    accepted, command, source_id = edit(service, alice, thread.id, "Edited")
    finish(service, alice, accepted.request)
    restored = switch(service, alice, thread.id, thread.id)
    with service.engine.begin() as conn:
        conn.execute(sa.update(t.connections).values(enabled=False))
    monkeypatch.setattr(service, "_consume_rate", lambda *_: pytest.fail("Replay consumed rate"))
    monkeypatch.setattr(service, "_attachment_assets", lambda *_: pytest.fail("Replay readmitted assets"))
    replay = admit_request(service, alice.bearer, alice.view.csrf_token, thread.id,
        command.model_copy(update={"expected_revision": 0}), source_id, edit=True)
    assert replay.created_branch == accepted.created_branch and replay.turn_id == accepted.turn_id
    assert replay.active_branch_id == thread.id and replay.revision == restored.revision
    assert replay.request.state == "completed" and len(provider.calls) == 2
    for changed in ({"text": "Исходный вопрос"}, {"source_attempt_id": accepted.request.id},
                    {"branch_id": accepted.created_branch.id}):
        with pytest.raises(ChatError, match="request_conflict"):
            admit_request(service, alice.bearer, alice.view.csrf_token, thread.id,
                command.model_copy(update=changed), source_id, edit=True)
    assert graph_page(service, alice.bearer, thread.id).active_branch_id == thread.id


@pytest.mark.parametrize("original,draft,kind", [
    ("A", "A", "same"), ("A", "\t A\r\n", "same"), ("A", "\u0085A\u0085", "same"),
    ("A", "\x1cA\x1f", "same"), ("A", "\u00a0\u2003A\u202f\u3000", "same"),
    ("A", "\ufeffA\ufeff", "edit"), ("A", "\u200bA\u200b", "edit"),
    ("A B", "A  B", "edit"), ("A\nB", "A\r\nB", "edit"), ("é", "e\u0301", "edit"),
    ("a", "A", "edit"), ("A" * 5999, " " + "A" * 5999, "same"),
    ("A" * 6000, " " + "A" * 6000, "invalid"),
    ("😀" * 5999, "😀" * 6000, "edit"), ("😀" * 6000, "😀" * 6001, "invalid"),
    ("A", "A\0", "invalid"), ("A", " \t ", "empty"),
], ids=["same", "strip", "nel", "c0", "unicode-space", "bom", "zero-width",
    "interior-space", "crlf", "nfd", "case", "raw-6000", "raw-6001",
    "astral-6000", "astral-6001", "nul", "empty"])
def test_d5_exact_normalization_and_raw_codepoint_bound(chat_env, original, draft, kind):
    service, alice, _, _ = chat_env
    connect_key(service, alice)
    thread = new_thread(service, alice)
    first = request(service, alice, thread.id, original)
    finish(service, alice, first)
    before = durable_rows(service)
    if kind == "invalid":
        with pytest.raises(ValidationError):
            edit_command(service, alice, thread.id, draft)
    elif kind in {"same", "empty"}:
        with pytest.raises(ChatError, match="message_unchanged" if kind == "same" else "invalid_input"):
            edit(service, alice, thread.id, draft)
    else:
        accepted, _, _ = edit(service, alice, thread.id, draft)
        assert graph_page(service, alice.bearer, thread.id).turns[-1].user_message.content == draft.strip()
        assert accepted.request.state == "pending"
        return
    assert durable_rows(service) == before


@pytest.mark.parametrize("inherited", [False, True])
def test_regenerate_replay_keeps_execution_projection_after_branch_change(chat_env, inherited):
    service, alice, _, _ = chat_env
    thread, _, provider = prepare(service, alice)
    source_turn = graph_page(service, alice.bearer, thread.id).turns[0].id
    if inherited:
        suffix = request(service, alice, thread.id, "Fork later")
        finish(service, alice, suffix)
        child, _, _ = edit(service, alice, thread.id, "Child suffix")
        finish(service, alice, child.request)
    accepted, command = regenerate(service, alice, thread.id, source_turn)
    finish(service, alice, accepted.request)
    replay = admit_request(service, alice.bearer, alice.view.csrf_token,
        thread.id, command, source_turn)
    assert replay.execution_branch_id == command.branch_id == replay.active_branch_id
    assert replay.turn.selected_attempt_id == accepted.request.id
    if inherited:
        switch(service, alice, thread.id, thread.id)
    else:
        child, _, _ = edit(service, alice, thread.id, "Replace source", source_turn)
        finish(service, alice, child.request)
        assert source_turn not in [turn.id for turn in graph_page(service, alice.bearer, thread.id).turns]
    current = graph_page(service, alice.bearer, thread.id)
    before, calls = durable_rows(service), len(provider.calls)
    replay = admit_request(service, alice.bearer, alice.view.csrf_token,
        thread.id, command, source_turn)
    assert replay.execution_branch_id == command.branch_id != current.active_branch_id
    assert replay.active_branch_id == current.active_branch_id and replay.revision == current.revision
    assert replay.turn.id == source_turn and replay.turn.selected_attempt_id == accepted.request.id
    assert replay.request.state == "completed" and len(provider.calls) == calls
    assert durable_rows(service) == before
