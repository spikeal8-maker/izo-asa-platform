"""Durable same-turn attempts, CAS and paid replay boundaries with fake providers."""
from uuid import uuid4

import pytest
import sqlalchemy as sa

from izo.catalog import tables as catalog
from izo.chat import tables as t
from izo.chat.graph_requests import admit_request
from izo.chat.graph_schemas import GraphRegenerate, GraphSelection
from izo.chat.graph_selection import change_selection
from izo.chat.history_pages import attempt_page, graph_page
from izo.chat.provider import ProviderFailure
from izo.chat.schemas import CredentialCommand, CredentialWrite
from izo.chat.service import ChatError
from test_chat import KEY, chat_env, connect_key, new_thread, request


class RecordingProvider:
    def __init__(self):
        self.calls = []
        self.failure = None

    def verify(self, key, timeout=15):
        assert key == KEY

    def stream(self, key, model, messages, max_tokens, timeout, stop):
        self.verify(key)
        self.calls.append(messages)
        if self.failure:
            raise ProviderFailure(self.failure)
        yield f"Вариант {len(self.calls)}"
        yield ": сохранённый ответ"


def prepare(service, alice):
    connect_key(service, alice)
    provider = RecordingProvider()
    service.provider = provider
    thread = new_thread(service, alice)
    first = request(service, alice, thread.id, "Исходный вопрос")
    assert "message.done" in "".join(service.stream_events(alice.bearer, first.id))
    return thread, first, provider


def command_for(service, alice, thread_id, turn_id=None):
    graph = graph_page(service, alice.bearer, thread_id)
    turn = graph.turns[-1] if turn_id is None else next(
        (item for item in graph.turns if item.id == turn_id), None)
    if turn is None:
        turn = attempt_page(service, alice.bearer, thread_id, turn_id).turn
    return turn, GraphRegenerate(request_id=uuid4(), branch_id=graph.active_branch_id,
        source_attempt_id=turn.selected_attempt_id, expected_revision=graph.revision)


def regenerate(service, alice, thread_id, turn_id=None):
    turn, command = command_for(service, alice, thread_id, turn_id)
    result = admit_request(service, alice.bearer, alice.view.csrf_token, thread_id, command, turn.id)
    return result, command


def select(service, alice, thread_id, turn_id, attempt_id, revision=None):
    graph = graph_page(service, alice.bearer, thread_id)
    return change_selection(service, alice.bearer, alice.view.csrf_token, thread_id, turn_id,
        GraphSelection(branch_id=graph.active_branch_id, attempt_id=attempt_id,
            expected_revision=graph.revision if revision is None else revision))


def test_regenerate_keeps_original_user_and_selected_answer_until_completed(chat_env):
    service, alice, _, _ = chat_env
    thread, first, provider = prepare(service, alice)
    original = service.thread_detail(alice.bearer, thread.id).messages
    accepted, command = regenerate(service, alice, thread.id)
    assert accepted.request.id == command.request_id != first.id
    assert accepted.turn.selected_attempt_id == first.id
    assert accepted.turn.latest_attempt.state == "pending"
    assert accepted.turn.completed_count == 1
    physical = service.thread_detail(alice.bearer, thread.id).messages
    assert physical[:2] == original and len(physical) == 3
    assert physical[-1].request_id == accepted.request.id
    assert "message.done" in "".join(service.stream_events(alice.bearer, accepted.request.id))
    projected = graph_page(service, alice.bearer, thread.id).turns[0]
    assert projected.user_message == original[0]
    assert projected.assistant_display_sequence == original[1].sequence
    assert projected.selected_attempt_id == accepted.request.id
    assert projected.selected_attempt.message.sequence == 3
    assert projected.completed_count == projected.selected_completed_position == 2
    assert projected.previous_completed_attempt_id == first.id
    assert len(provider.calls) == 2


def test_replay_retains_attempt_without_readmission_and_rejects_different_intent(chat_env):
    service, alice, _, _ = chat_env
    thread, first, provider = prepare(service, alice)
    accepted, command = regenerate(service, alice, thread.id)
    list(service.stream_events(alice.bearer, accepted.request.id))
    service.model_admission = lambda model: (_ for _ in ()).throw(AssertionError("no readmission"))
    with service.engine.begin() as conn:
        conn.execute(sa.update(catalog.models).where(catalog.models.c.id == first.model).values(enabled=False))
        conn.execute(sa.update(catalog.state).values(default_model="deepseek-v4-pro"))
    replay = admit_request(service, alice.bearer, alice.view.csrf_token, thread.id, command, accepted.turn.id)
    assert replay.request.id == accepted.request.id and replay.request.state == "completed"
    assert "message.done" in "".join(service.stream_events(alice.bearer, replay.request.id))
    assert len(provider.calls) == 2
    with pytest.raises(ChatError, match="request_conflict"):
        admit_request(service, alice.bearer, alice.view.csrf_token, thread.id,
            command.model_copy(update={"source_attempt_id": accepted.request.id}), accepted.turn.id)
    with pytest.raises(ChatError, match="request_conflict"):
        request(service, alice, thread.id, "Исходный вопрос", request_id=accepted.request.id)
    with pytest.raises(ChatError, match="model_not_allowed"):
        regenerate(service, alice, thread.id)


def test_fresh_credential_generation_and_completed_only_cas(chat_env):
    service, alice, _, _ = chat_env
    thread, first, _ = prepare(service, alice)
    credential = service.credential(alice.bearer)
    saved = service.save_credential(alice.bearer, alice.view.csrf_token,
        CredentialWrite(operation_id=uuid4(), key=KEY, expected_revision=credential.revision))
    service.verify_credential(alice.bearer, alice.view.csrf_token,
        CredentialCommand(operation_id=uuid4(), expected_revision=saved.revision))
    accepted, _ = regenerate(service, alice, thread.id)
    with service.engine.begin() as conn:
        generations = dict(conn.execute(sa.select(t.requests.c.id, t.requests.c.credential_generation)).all())
    assert generations[first.id] == 1 and generations[accepted.request.id] == 2
    with pytest.raises(ChatError, match="attempt_not_completed"):
        select(service, alice, thread.id, accepted.turn.id, accepted.request.id)
    old_revision = accepted.revision
    list(service.stream_events(alice.bearer, accepted.request.id))
    with pytest.raises(ChatError, match="graph_revision_conflict"):
        select(service, alice, thread.id, accepted.turn.id, first.id, old_revision)
    changed = select(service, alice, thread.id, accepted.turn.id, first.id)
    unchanged = select(service, alice, thread.id, accepted.turn.id, first.id)
    assert unchanged.revision == changed.revision and unchanged.turn.selected_completed_position == 1
    assert unchanged.turn.next_completed_attempt_id == accepted.request.id


@pytest.mark.parametrize("failure", ["provider_rejected", "provider_rate_limited", "provider_connection_failed"])
def test_failed_regenerate_keeps_selection_and_unknown_blocks_new_execution(chat_env, failure):
    service, alice, _, _ = chat_env
    thread, first, provider = prepare(service, alice)
    provider.failure = failure
    accepted, command = regenerate(service, alice, thread.id)
    events = "".join(service.stream_events(alice.bearer, accepted.request.id))
    assert "message.error" in events
    graph = graph_page(service, alice.bearer, thread.id)
    assert graph.turns[0].selected_attempt_id == first.id
    assert graph.turns[0].completed_count == 1 and graph.turns[0].latest_attempt.state == "error"
    replay = admit_request(service, alice.bearer, alice.view.csrf_token, thread.id, command, accepted.turn.id)
    list(service.stream_events(alice.bearer, replay.request.id))
    assert len(provider.calls) == 2
    if failure == "provider_connection_failed":
        assert graph.unknown_request_id == accepted.request.id
        with pytest.raises(ChatError, match="provider_outcome_unknown"):
            regenerate(service, alice, thread.id)
        with pytest.raises(ChatError, match="provider_outcome_unknown"):
            request(service, alice, thread.id, "Нельзя повторно платить")
    else:
        assert graph.unknown_request_id is None
        next_attempt, _ = regenerate(service, alice, thread.id)
        assert next_attempt.request.id != accepted.request.id


def test_pending_stop_and_late_partial_do_not_replace_completed_content(chat_env):
    service, alice, _, _ = chat_env
    thread, first, provider = prepare(service, alice)
    pending, _ = regenerate(service, alice, thread.id)
    service.stop(alice.bearer, alice.view.csrf_token, pending.request.id)
    list(service.stream_events(alice.bearer, pending.request.id))
    assert len(provider.calls) == 1
    completed, _ = regenerate(service, alice, thread.id)
    list(service.stream_events(alice.bearer, completed.request.id))
    original = graph_page(service, alice.bearer, thread.id).turns[0].selected_attempt.message
    service._save_partial(completed.request.id, "Поздняя запись не должна попасть в ответ")
    assert graph_page(service, alice.bearer, thread.id).turns[0].selected_attempt.message == original
    select(service, alice, thread.id, completed.turn.id, first.id)
    assert service._finish(completed.request.id, "completed", None, "late finish") == "completed"
    assert graph_page(service, alice.bearer, thread.id).turns[0].selected_attempt_id == first.id


def test_attempt_page_is_bounded_and_preserves_selected_outside_page(chat_env):
    service, alice, _, _ = chat_env
    thread, first, _ = prepare(service, alice)
    turn_id = graph_page(service, alice.bearer, thread.id).turns[0].id
    for _ in range(23):
        with service.engine.begin() as conn:
            conn.execute(sa.delete(t.limits))
        accepted, _ = regenerate(service, alice, thread.id)
        list(service.stream_events(alice.bearer, accepted.request.id))
    select(service, alice, thread.id, turn_id, first.id)
    latest = attempt_page(service, alice.bearer, thread.id, turn_id)
    assert len(latest.attempts) == 20 and latest.next_before_ordinal == 5
    assert latest.turn.selected_attempt.id == first.id
    assert latest.turn.completed_count == 24 and latest.turn.selected_completed_position == 1
    oldest = attempt_page(service, alice.bearer, thread.id, turn_id, latest.next_before_ordinal)
    assert [item.ordinal for item in oldest.attempts] == [1, 2, 3, 4]
    assert oldest.next_before_ordinal is None
