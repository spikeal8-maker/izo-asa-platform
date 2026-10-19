"""Frozen selected prefixes, immutable history and legacy claim provenance."""
import pytest
import sqlalchemy as sa

from izo.chat import tables as t
from izo.chat.graph_context import MAX_CONTEXT_CHARS
from izo.chat.history_pages import graph_page
from izo.chat.service import ChatError, ChatService
from test_chat import chat_env, new_thread, request
from test_chat_graph_migration import upgrade_legacy
from test_chat_graph_requests import RecordingProvider, prepare, regenerate, select
from test_chat_vision import asset, submit, vision_env


def finish(service, alice, created):
    assert "message.done" in "".join(service.stream_events(alice.bearer, created.id))


def test_next_send_freezes_chosen_answer_at_admission_not_later_selection(chat_env):
    service, alice, _, _ = chat_env
    thread, first, provider = prepare(service, alice)
    alternate, _ = regenerate(service, alice, thread.id)
    finish(service, alice, alternate.request)
    select(service, alice, thread.id, alternate.turn.id, first.id)
    sent = request(service, alice, thread.id, "Продолжение выбранной версии")
    select(service, alice, thread.id, alternate.turn.id, alternate.request.id)
    finish(service, alice, sent)
    assert [item["content"] for item in provider.calls[-1][1:]] == [
        "Исходный вопрос", "Вариант 1: сохранённый ответ", "Продолжение выбранной версии"]
    graph = graph_page(service, alice.bearer, thread.id)
    assert graph.turns[0].selected_attempt_id == alternate.request.id
    following = request(service, alice, thread.id, "Теперь другая версия")
    finish(service, alice, following)
    assert provider.calls[-1][2]["content"] == "Вариант 2: сохранённый ответ"


def test_regenerating_earlier_turn_excludes_own_alternatives_and_later_suffix(chat_env):
    service, alice, _, _ = chat_env
    thread, _, provider = prepare(service, alice)
    middle = request(service, alice, thread.id, "Средний вопрос")
    finish(service, alice, middle)
    later = request(service, alice, thread.id, "Поздний вопрос")
    finish(service, alice, later)
    graph = graph_page(service, alice.bearer, thread.id)
    regenerated, _ = regenerate(service, alice, thread.id, graph.turns[1].id)
    finish(service, alice, regenerated.request)
    assert [item["content"] for item in provider.calls[-1][1:]] == [
        "Исходный вопрос", "Вариант 1: сохранённый ответ", "Средний вопрос"]
    first_again, _ = regenerate(service, alice, thread.id, graph.turns[0].id)
    finish(service, alice, first_again.request)
    assert provider.calls[-1][1:] == [{"role": "user", "content": "Исходный вопрос"}]
    reloaded = graph_page(service, alice.bearer, thread.id)
    assert reloaded.turns[-1].selected_attempt_id == later.id
    assert reloaded.turns[1].selected_attempt_id == regenerated.request.id


def test_context_budget_drops_whole_old_turns_without_orphaned_messages(chat_env):
    service, alice, _, _ = chat_env
    thread, _, provider = prepare(service, alice)

    class LongAnswer(RecordingProvider):
        def stream(self, key, model, messages, max_tokens, timeout, stop):
            self.calls.append(messages)
            yield "Д" * (MAX_CONTEXT_CHARS - 100)

    service.provider = LongAnswer()
    large = request(service, alice, thread.id, "Большой ответ")
    finish(service, alice, large)
    service.provider = provider
    current = request(service, alice, thread.id, "Н" * 200)
    finish(service, alice, current)
    assert provider.calls[-1][1:] == [{"role": "user", "content": "Н" * 200}]


@pytest.mark.parametrize("corruption", ["snapshot", "message"])
def test_context_corruption_fails_before_paid_marker_or_provider_call(chat_env, corruption):
    service, alice, _, _ = chat_env
    thread, first, provider = prepare(service, alice)
    accepted, _ = regenerate(service, alice, thread.id)
    with service.engine.begin() as conn:
        if corruption == "snapshot":
            conn.execute(sa.update(t.contexts).where(t.contexts.c.request_id == accepted.request.id)
                .values(digest="0" * 64))
        else:
            conn.execute(sa.update(t.messages).where(t.messages.c.id == accepted.turn.user_message.id)
                .values(content="Unexpected storage corruption"))
    events = "".join(service.stream_events(alice.bearer, accepted.request.id))
    assert "message.error" in events and "provider_outcome_unknown" not in events
    assert len(provider.calls) == 1
    assert service.request(alice.bearer, accepted.request.id).error_code in {
        "context_unavailable", "context_integrity_error"}
    assert graph_page(service, alice.bearer, thread.id).turns[0].selected_attempt_id == first.id


def test_legacy_pending_records_honest_claim_snapshot_before_paid_marker(chat_env, monkeypatch):
    service, alice, _, _ = chat_env
    thread, first, provider = prepare(service, alice)
    pending = request(service, alice, thread.id, "Незавершённый старый запрос")
    upgrade_legacy(service)
    with service.engine.begin() as conn:
        before = conn.execute(sa.select(t.contexts).where(
            t.contexts.c.request_id == pending.id)).mappings().one()
        assert before["provenance"] == "legacy_unrecorded" and before["snapshot"] is None
    original_mark = service._mark_paid_submission

    def mark(request_id):
        with service.engine.begin() as conn:
            captured = conn.execute(sa.select(t.contexts).where(
                t.contexts.c.request_id == request_id)).mappings().one()
            assert captured["provenance"] == "legacy_claim"
            assert captured["snapshot"] and captured["digest"] and captured["revision"] == 0
            old = conn.execute(sa.select(t.contexts).where(
                t.contexts.c.request_id == first.id)).mappings().one()
            assert old["provenance"] == "legacy_unrecorded" and old["snapshot"] is None
        original_mark(request_id)

    monkeypatch.setattr(service, "_mark_paid_submission", mark)
    finish(service, alice, pending)
    assert [item["content"] for item in provider.calls[-1][1:]] == [
        "Исходный вопрос", "Вариант 1: сохранённый ответ", "Незавершённый старый запрос"]


def test_restart_derives_attempt_outcome_without_losing_previous_selection(chat_env):
    service, alice, _, clock = chat_env
    thread, first, provider = prepare(service, alice)
    accepted, command = regenerate(service, alice, thread.id)
    unconsumed = service.stream_events(alice.bearer, accepted.request.id)
    service._mark_paid_submission(accepted.request.id)
    restarted = ChatService(service.auth, service.policy, provider, clock=lambda: clock[0])
    graph = graph_page(restarted, alice.bearer, thread.id)
    assert graph.unknown_request_id == accepted.request.id
    assert graph.turns[0].selected_attempt_id == first.id
    assert graph.turns[0].latest_attempt.state == "interrupted"
    assert "provider_outcome_unknown" in "".join(restarted.stream_events(alice.bearer, command.request_id))
    assert len(provider.calls) == 1
    with pytest.raises(ChatError, match="provider_outcome_unknown"):
        regenerate(restarted, alice, thread.id)
    unconsumed.close()


def test_regenerate_reuses_owned_image_snapshots_and_rechecks_vision(vision_env, monkeypatch):
    service, alice, _, _, objects = vision_env
    provider = RecordingProvider()
    service.provider = provider
    uid = asset(service, alice, objects)
    thread = new_thread(service, alice)
    first = submit(service, alice, thread, [uid], text="Исходное изображение")
    finish(service, alice, first)
    accepted, _ = regenerate(service, alice, thread.id)
    finish(service, alice, accepted.request)
    assert provider.calls[0] == provider.calls[1]
    with service.engine.begin() as conn:
        assert conn.execute(sa.select(sa.func.count()).select_from(t.attachments)).scalar_one() == 1
    monkeypatch.setattr(service, "static_vision_supported", lambda *_: False)
    with pytest.raises(ChatError, match="model_vision_unsupported"):
        regenerate(service, alice, thread.id)


def test_graph_keyset_uses_immutable_turns_while_legacy_cursor_remains_physical(chat_env):
    service, alice, _, _ = chat_env
    thread, _, _ = prepare(service, alice)
    first_turn = graph_page(service, alice.bearer, thread.id).turns[0]
    for index in range(51):
        with service.engine.begin() as conn:
            conn.execute(sa.delete(t.limits))
        sent = request(service, alice, thread.id, f"Question {index}")
        finish(service, alice, sent)
    newest = graph_page(service, alice.bearer, thread.id)
    physical = service.thread_detail(alice.bearer, thread.id)
    assert len(newest.turns) == 50 and newest.next_before_turn_sequence == 5
    regenerated, _ = regenerate(service, alice, thread.id, first_turn.id)
    finish(service, alice, regenerated.request)
    older = graph_page(service, alice.bearer, thread.id, newest.next_before_turn_sequence)
    assert [turn.turn_sequence for turn in older.turns] == [1, 3]
    assert older.next_before_turn_sequence is None
    assert older.turns[0].assistant_display_sequence == 2
    assert older.turns[0].selected_attempt.message.sequence == 105
    assert older.turns[0].selected_attempt_id == regenerated.request.id
    legacy = service.older_messages(alice.bearer, thread.id, physical.next_before_sequence)
    assert [message.sequence for message in legacy.messages] == [1, 2, 3, 4]
    assert all(message.sequence < physical.next_before_sequence for message in legacy.messages)
    assert not set(turn.id for turn in newest.turns) & set(turn.id for turn in older.turns)


def pg_completion_and_projection_locks(environment):
    from concurrent.futures import ThreadPoolExecutor
    from test_chat_graph_http import PGGateProvider, pg_wait_blocked
    service, alice, _, _ = environment
    thread, first, _ = prepare(service, alice)
    second, _ = regenerate(service, alice, thread.id)
    finish(service, alice, second.request)
    select(service, alice, thread.id, second.turn.id, first.id)
    third, _ = regenerate(service, alice, thread.id)
    gate = PGGateProvider()
    service.provider = gate
    with ThreadPoolExecutor(max_workers=3) as pool:
        execution = pool.submit(lambda: list(service.stream_events(alice.bearer, third.request.id)))
        assert gate.entered.wait(10)
        manual = select(service, alice, thread.id, third.turn.id, second.request.id)
        with service.engine.begin() as holder:
            holder.execute(sa.select(t.threads.c.id).where(t.threads.c.id == thread.id).with_for_update())
            gate.release.set()
            pg_wait_blocked(service, 1)
            # Completion must still be waiting for Thread, without holding Request.
            with service.engine.begin() as probe:
                probe.execute(sa.select(t.requests.c.id).where(
                    t.requests.c.id == third.request.id).with_for_update(nowait=True))
            partial = pool.submit(service._save_partial, third.request.id, "late stale partial")
            projection = pool.submit(graph_page, service, alice.bearer, thread.id)
            pg_wait_blocked(service, 3)
        assert "message.done" in "".join(execution.result(timeout=15))
        partial.result(timeout=15)
        observed = projection.result(timeout=15)
    assert observed.revision == manual.revision + 1
    assert observed.turns[0].selected_attempt_id == third.request.id
    assert observed.turns[0].selected_attempt.message.content == "Durable PostgreSQL answer"
    latest = select(service, alice, thread.id, third.turn.id, first.id)
    assert latest.revision == observed.revision + 1 and latest.turn.selected_attempt_id == first.id
