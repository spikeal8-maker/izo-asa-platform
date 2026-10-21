"""Exercise disposable-container ownership and cancellation without Docker or network."""
import signal
import subprocess
import sys

import pytest

from tools import chat_thread_search_postgres_ci as ci

CONTAINER = "a" * 64
EXPECTED_ENV = {
    "IZO_ENVIRONMENT": "test", "IZO_CHAT_GRAPH_ACCEPTANCE": "isolated",
    "IZO_PG_HOST": "127.0.0.1", "IZO_PG_USER": "izo_search_ci",
    "IZO_PG_DATABASE": "izo_search_ci", "IZO_PG_PASSWORD": "izo-search-ci-disposable",
    "PYTHONPATH": "apps/api:tests:.", "PYTHONDONTWRITEBYTECODE": "1", "IZO_PG_PORT": "45432",
}


class ContainerCommands:
    def __init__(self):
        self.calls, self.removed, self.sleeps = [], [], []
        self.health, self.probes = ["healthy"], 0
        self.exists, self.owner, self.name = False, "", ""
        self.start_failure, self.runner_code, self.remove_code = None, 0, 0
        self.binding, self.returned_id, self.cleanup_identity = "127.0.0.1:45432", CONTAINER, None
        self.signal_at, self.signum = None, signal.SIGTERM
        self.runner = None

    def interrupt(self, stage):
        if self.signal_at == stage:
            signal.raise_signal(self.signum)

    def __call__(self, command, **kwargs):
        self.calls.append((command, kwargs))
        if command[0] != "docker":
            self.runner = (command, kwargs)
            self.interrupt("runner")
            return subprocess.CompletedProcess(command, self.runner_code)
        action = command[1]
        code, output = 0, ""
        if action == "run":
            self.name = command[command.index("--name") + 1]
            self.owner = command[command.index("--label") + 1].split("=", 1)[1]
            self.exists = self.start_failure != "before_create"
            if self.start_failure == "collision":
                self.owner = "foreign-owner"
            self.interrupt("create")
            code = 125 if self.start_failure else 0
            output = self.returned_id
        elif action == "inspect" and command[3] == "{{.State.Health.Status}}":
            self.probes += 1
            self.interrupt("readiness")
            output = self.health[min(self.probes - 1, len(self.health) - 1)]
        elif action == "inspect":
            assert command[-1] == self.name
            code = 0 if self.exists else 1
            output = self.cleanup_identity or f"{CONTAINER} {self.owner}"
        elif action == "port":
            assert command[2:] == [CONTAINER, "5432/tcp"]
            output = self.binding
        elif action == "rm":
            assert command[2:] == ["--force", "--volumes", CONTAINER]
            self.removed.append(command[-1])
            self.interrupt("cleanup")
            code = self.remove_code
        else:
            pytest.fail(f"Unexpected command: {command}")
        if code and kwargs.get("check"):
            raise subprocess.CalledProcessError(code, command, stderr="synthetic Docker failure")
        return subprocess.CompletedProcess(command, code, stdout=output, stderr="")


@pytest.fixture
def commands(monkeypatch):
    original_handlers = {item: signal.getsignal(item) for item in (signal.SIGINT, signal.SIGTERM)}
    for key, value in EXPECTED_ENV.items():
        monkeypatch.setenv(key, value if key in ci.ISOLATED else "untrusted-inherited-value")
    monkeypatch.setenv("GITHUB_RUN_ID", "1234")
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "2")
    monkeypatch.setenv("IZO_CI_TEST_SENTINEL", "preserved")
    fake = ContainerCommands()
    monkeypatch.setattr(ci.subprocess, "run", fake)
    monkeypatch.setattr(ci.time, "sleep", fake.sleeps.append)
    yield fake
    assert all(signal.getsignal(item) == handler for item, handler in original_handlers.items())


def test_healthy_container_preserves_original_runner_environment_and_limits(commands):
    commands.health = ["starting", "healthy"]
    assert ci.main() == 0
    command = commands.calls[0][0]
    assert command[:5] == ["docker", "run", "--detach", "--rm", "--pull=never"]
    assert command[-1] == "postgres:17-bookworm"
    assert command[command.index("--publish") + 1] == "127.0.0.1::5432"
    assert commands.name.startswith("izo-search-1234-2-") and len(commands.owner) == 32
    assert command[command.index("--label") + 1] == f"{ci.OWNER_LABEL}={commands.owner}"
    assert {command[index + 1] for index, item in enumerate(command) if item == "--env"} == {
        "POSTGRES_USER=izo_search_ci", "POSTGRES_DB=izo_search_ci",
        "POSTGRES_PASSWORD=izo-search-ci-disposable",
    }
    assert {item for item in command if item.startswith("--health-")} == {
        "--health-cmd=pg_isready -h 127.0.0.1 -p 5432 -U izo_search_ci -d izo_search_ci",
        "--health-interval=1s", "--health-timeout=3s", "--health-retries=30",
    }
    runner, options = commands.runner
    assert runner == [sys.executable, "-B", "tests/test_chat_thread_search_postgres.py"]
    assert options.keys() == {"cwd", "env"}  # Preserve runner stdout/stderr in CI.
    assert options["cwd"] == ci.ROOT
    assert {key: options["env"][key] for key in EXPECTED_ENV} == EXPECTED_ENV
    assert options["env"]["IZO_CI_TEST_SENTINEL"] == "preserved"
    assert commands.probes == 2 and commands.sleeps == [1]
    assert commands.removed == [CONTAINER]


@pytest.mark.parametrize("key,value", [
    ("IZO_ENVIRONMENT", None), ("IZO_ENVIRONMENT", "production"),
    ("IZO_CHAT_GRAPH_ACCEPTANCE", None), ("IZO_CHAT_GRAPH_ACCEPTANCE", "enabled"),
    ("GITHUB_RUN_ID", None), ("GITHUB_RUN_ID", "../other"),
    ("GITHUB_RUN_ATTEMPT", ""), ("GITHUB_RUN_ATTEMPT", "-1"),
])
def test_unisolated_or_unidentified_invocations_fail_before_docker(commands, monkeypatch, key, value):
    if value is None:
        monkeypatch.delenv(key)
    else:
        monkeypatch.setenv(key, value)
    assert ci.main() == 2
    assert not commands.calls


@pytest.mark.parametrize("health,probes,sleeps", [
    (["starting", "unhealthy"], 2, 1), (["starting"], 45, 45),
])
def test_readiness_failure_is_bounded_and_cleans_owned_container(commands, health, probes, sleeps):
    commands.health = health
    assert ci.main() == 1
    assert commands.probes == probes and commands.sleeps == [1] * sleeps
    assert commands.runner is None and commands.removed == [CONTAINER]


@pytest.mark.parametrize("runner_code,expected", [(7, 7), (-2, 130), (-15, 143)])
def test_runner_failure_and_signals_are_not_hidden(commands, runner_code, expected):
    commands.runner_code = runner_code
    assert ci.main() == expected
    assert commands.removed == [CONTAINER]


@pytest.mark.parametrize("failure,owned", [
    ("before_create", False), ("after_create", True), ("collision", False),
])
def test_start_failure_cleans_only_a_container_created_by_this_invocation(commands, failure, owned):
    commands.start_failure = failure
    assert ci.main() == 125
    assert commands.removed == ([CONTAINER] if owned else [])
    assert commands.runner is None


def test_malformed_run_output_still_cleans_an_owned_created_container(commands):
    commands.returned_id = "not-a-container-id"
    assert ci.main() == 1
    assert commands.removed == [CONTAINER] and commands.runner is None


@pytest.mark.parametrize("identity", [
    f"{CONTAINER} foreign-owner", "malformed-id owner", "", "extra fields are rejected",
])
def test_cleanup_refuses_unverified_identity(commands, identity):
    commands.cleanup_identity = identity or " "
    assert ci.main() == 1
    assert not commands.removed


def test_cleanup_refuses_replaced_container_even_with_the_original_label(commands, monkeypatch):
    commands.cleanup_identity = "b" * 64 + " owner"
    monkeypatch.setattr(ci, "uuid4", lambda: type("Owner", (), {"hex": "owner"})())
    assert ci.main() == 1
    assert not commands.removed


@pytest.mark.parametrize("binding", [
    "0.0.0.0:45432", "[::1]:45432", "127.0.0.1:0", "127.0.0.1:65536",
    "127.0.0.1:45432\n0.0.0.0:45432",
])
def test_invalid_port_binding_fails_before_the_runner(commands, binding):
    commands.binding = binding
    assert ci.main() == 1
    assert commands.runner is None and commands.removed == [CONTAINER]


@pytest.mark.parametrize("stage", ["create", "readiness", "runner"])
@pytest.mark.parametrize("signum", [signal.SIGINT, signal.SIGTERM])
def test_actual_signal_cancellation_cleans_ownership_and_preserves_exit_code(commands, stage, signum):
    commands.signal_at, commands.signum = stage, signum
    assert ci.main() == 128 + signum
    assert commands.removed == [CONTAINER]


@pytest.mark.parametrize("runner_code,expected", [(0, 1), (7, 7)])
def test_cleanup_failure_is_visible_without_hiding_the_original_failure(commands, runner_code, expected):
    commands.runner_code, commands.remove_code = runner_code, 1
    assert ci.main() == expected
    assert commands.removed == [CONTAINER]


def test_cleanup_ignores_repeated_cancellation_until_owned_removal_finishes(commands):
    commands.runner_code = 143
    commands.signal_at = "cleanup"
    assert ci.main() == 143
    assert commands.removed == [CONTAINER]


def test_workflow_keeps_explicit_isolation_and_existing_timeout():
    workflow = (ci.ROOT / ".github/workflows/ci.yml").read_text()
    block = workflow.split("      - name: Chat thread search PostgreSQL acceptance\n", 1)[1]
    block = block.split("      - name:", 1)[0]
    assert "        timeout-minutes: 5\n" in block
    assert "          IZO_ENVIRONMENT: test\n" in block
    assert "          IZO_CHAT_GRAPH_ACCEPTANCE: isolated\n" in block
    assert "run: .venv/bin/python -B tools/chat_thread_search_postgres_ci.py\n" in block
