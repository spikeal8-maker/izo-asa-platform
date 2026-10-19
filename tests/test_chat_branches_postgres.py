"""Real PostgreSQL branch admission, selection and completion contenders."""
from uuid import uuid4

import pytest
import sqlalchemy as sa

from izo.chat import tables as t
from izo.chat.branches import change_branch
from izo.chat.graph_requests import admit_request
from izo.chat.graph_schemas import BranchSelection
from test_chat import request
from test_chat_branches import durable_rows, edit, edit_command, switch
from test_chat_graph_context import finish
from test_chat_graph_requests import prepare


def pg_branch_contenders(environment, mode):
    from izo.chat.schemas import RequestCreate
    from test_chat_graph_http import pg_parallel
    service, alice, _, _ = environment
    thread, _, _ = prepare(service, alice)
    child, _, _ = edit(service, alice, thread.id, "Existing child")
    finish(service, alice, child.request)
    switch(service, alice, thread.id, thread.id)
    source, command = edit_command(service, alice, thread.id,
        "Исходный вопрос" if mode == "unchanged" else "Concurrent edit")
    def invoke(value):
        return lambda: admit_request(service, alice.bearer, alice.view.csrf_token,
            thread.id, value, source, edit=True)
    second = invoke(command if mode == "same" else command.model_copy(update={"request_id": uuid4()}))
    if mode == "send":
        body = RequestCreate(request_id=uuid4(), model="deepseek-flash", text="Concurrent send",
            branch_id=command.branch_id, expected_revision=command.expected_revision)
        second = lambda: service.create_request(alice.bearer, alice.view.csrf_token, thread.id, body)
    if mode == "switch":
        body = BranchSelection(branch_id=command.branch_id, expected_revision=command.expected_revision,
            target_branch_id=child.created_branch.id)
        second = lambda: change_branch(service, alice.bearer, alice.view.csrf_token, thread.id, body)
    before = durable_rows(service)
    results = pg_parallel(service, thread.id, [invoke(command), second])
    if mode == "unchanged":
        assert results == ["message_unchanged", "message_unchanged"]
        assert durable_rows(service) == before
    elif mode == "same":
        assert results[0] == results[1]
        assert len(durable_rows(service)[t.branches.name]) == len(before[t.branches.name]) + 1
        assert len(durable_rows(service)[t.requests.name]) == len(before[t.requests.name]) + 1
    else:
        assert sum(isinstance(result, str) for result in results) == 1
        assert "graph_revision_conflict" in results

def pg_edit_vs_manual_selection(environment):
    from izo.chat.graph_requests import admit_request
    from izo.chat.graph_selection import change_selection
    from izo.chat.graph_schemas import GraphSelection
    from test_chat_branches import edit, edit_command
    from test_chat_graph_context import finish
    from test_chat_graph_requests import prepare, regenerate, select
    from test_chat_graph_http import pg_parallel
    service, alice, _, _ = environment
    thread, first, _ = prepare(service, alice)
    second, _ = regenerate(service, alice, thread.id)
    finish(service, alice, second.request)
    select(service, alice, thread.id, second.turn.id, first.id)
    finish(service, alice, request(service, alice, thread.id, "Parent suffix"))
    child, _, _ = edit(service, alice, thread.id, "Child suffix")
    finish(service, alice, child.request)
    source, command = edit_command(service, alice, thread.id, "Concurrent edit")
    selection = GraphSelection(branch_id=command.branch_id, expected_revision=command.expected_revision,
        attempt_id=second.request.id)
    results = pg_parallel(service, thread.id, [
        lambda: admit_request(service, alice.bearer, alice.view.csrf_token, thread.id, command, source, edit=True),
        lambda: change_selection(service, alice.bearer, alice.view.csrf_token, thread.id, second.turn.id, selection)])
    assert sum(isinstance(result, str) for result in results) == 1 and "graph_revision_conflict" in results
    accepted, expected = results[0], first.id
    if isinstance(accepted, str):
        accepted, _, _ = edit(service, alice, thread.id, "Concurrent edit")
        expected = second.request.id
    with service.engine.begin() as conn:
        message = conn.execute(sa.select(t.attempts.c.assistant_message_id).where(t.attempts.c.id == expected)).scalar_one()
        snapshot = conn.execute(sa.select(t.contexts.c.snapshot).where(t.contexts.c.request_id == accepted.request.id)).scalar_one()
    assert [item["id"] for item in snapshot["messages"] if item["role"] == "assistant"] == [str(message)]
    finish(service, alice, accepted.request)


def pg_switch_vs_completion(environment):
    from concurrent.futures import ThreadPoolExecutor
    from izo.chat.branches import change_branch
    from izo.chat.graph_schemas import BranchSelection
    from izo.chat.service import ChatError
    from test_chat_branches import edit, switch
    from test_chat_graph_http import PGGateProvider, pg_wait_blocked
    from test_chat_graph_requests import prepare

    class CompletionGate(PGGateProvider):
        """Pause after the consumer processed the chunk, just before provider EOF."""
        def stream(self, key, model, messages, max_tokens, timeout, stop):
            self.verify(key)
            self.calls.append(messages)
            yield "Durable PostgreSQL answer"
            self.entered.set()
            assert self.release.wait(20), "PG completion gate timed out"

    service, alice, _, _ = environment
    thread, first, _ = prepare(service, alice)
    accepted, _, _ = edit(service, alice, thread.id, "Completing child")
    command = BranchSelection(branch_id=accepted.active_branch_id, expected_revision=accepted.revision,
        target_branch_id=thread.id)
    gate = CompletionGate()
    service.provider = gate
    with ThreadPoolExecutor(max_workers=2) as pool:
        execution = pool.submit(lambda: list(service.stream_events(alice.bearer, accepted.request.id)))
        assert gate.entered.wait(10)
        with service.engine.begin() as holder:
            holder.execute(sa.select(t.threads.c.id).where(t.threads.c.id == thread.id).with_for_update())
            selection = pool.submit(change_branch, service, alice.bearer, alice.view.csrf_token, thread.id, command)
            gate.release.set()
            pg_wait_blocked(service, 2)
            with service.engine.begin() as probe:
                probe.execute(sa.select(t.requests.c.id).where(t.requests.c.id == accepted.request.id).with_for_update(nowait=True))
        with pytest.raises(ChatError) as error:
            selection.result(timeout=15)
        assert error.value.code in {"active_request_exists", "graph_revision_conflict"}
        assert "message.done" in "".join(execution.result(timeout=15))
    restored = switch(service, alice, thread.id, thread.id)
    assert restored.turns[0].selected_attempt_id == first.id
    child = switch(service, alice, thread.id, accepted.active_branch_id)
    assert child.turns[-1].selected_attempt_id == accepted.request.id

def run_postgres():
    from test_chat_branches_migration import (
        test_0019_retains_recorded_graph_and_branch_selection,
        test_0019_rejects_foreign_membership_and_ancestry,
        test_edit_rollback_retains_all_rows,
    )
    from test_chat_graph_migration import pg_environment
    from test_chat_branches import test_inherited_manual_selection_and_execution_are_branch_local
    cases = [("branches_0019_retention", test_0019_retains_recorded_graph_and_branch_selection),
        ("branches_relational_boundaries", test_0019_rejects_foreign_membership_and_ancestry),
        ("branches_inherited_selection", test_inherited_manual_selection_and_execution_are_branch_local),
        ("branches_atomic_rollback", test_edit_rollback_retains_all_rows),
        ("branches_edit_vs_manual_selection", pg_edit_vs_manual_selection),
        ("branches_switch_vs_completion", pg_switch_vs_completion)]
    cases += [("branches_race_" + mode, lambda e, m=mode: pg_branch_contenders(e, m))
              for mode in ("same", "distinct", "unchanged", "send", "switch")]
    for name, check in cases:
        with pg_environment() as environment:
            check(environment)
        print("POSTGRES_PASS " + name, flush=True)
    print(f"POSTGRES_BRANCH_PASS cases={len(cases)}", flush=True)
