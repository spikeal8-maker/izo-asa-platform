"""Run isolated search acceptance against one disposable, locally cached PostgreSQL."""
from pathlib import Path
import os
import re
import signal
import subprocess
import sys
import time
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
OWNER_LABEL = "izo.search-ci.owner"
ISOLATED = {
    "IZO_ENVIRONMENT": "test", "IZO_CHAT_GRAPH_ACCEPTANCE": "isolated",
}
POSTGRES_ENV = {
    "IZO_PG_HOST": "127.0.0.1", "IZO_PG_USER": "izo_search_ci",
    "IZO_PG_DATABASE": "izo_search_ci", "IZO_PG_PASSWORD": "izo-search-ci-disposable",
    "PYTHONPATH": "apps/api:tests:.", "PYTHONDONTWRITEBYTECODE": "1",
}


def docker(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["docker", *args], check=check, capture_output=True, text=True)


def cleanup(name: str, owner: str, created: str | None) -> bool:
    """A failed/interrupted run can create a container before returning its ID."""
    found = docker("inspect", "--format", '{{.Id}} {{index .Config.Labels "'
                   + OWNER_LABEL + '"}}', name, check=False)
    if found.returncode:
        return not created
    fields = found.stdout.strip().split()
    if (len(fields) != 2 or not re.fullmatch(r"[0-9a-f]{64}", fields[0]) or fields[1] != owner
            or created is not None and fields[0] != created):
        print("Refusing cleanup of an unowned PostgreSQL container", file=sys.stderr)
        return False
    return docker("rm", "--force", "--volumes", fields[0], check=False).returncode == 0


def cancel(signum: int, _frame) -> None:
    raise SystemExit(128 + signum)


def main() -> int:
    env = dict(os.environ)
    if any(env.get(key) != value for key, value in ISOLATED.items()):
        print("Explicit isolated/test PostgreSQL configuration is required", file=sys.stderr)
        return 2
    env.update(POSTGRES_ENV)
    run_id, attempt = env.get("GITHUB_RUN_ID", ""), env.get("GITHUB_RUN_ATTEMPT", "")
    if not re.fullmatch(r"[0-9]+", run_id) or not re.fullmatch(r"[0-9]+", attempt):
        print("GitHub run identity is required", file=sys.stderr)
        return 2
    owner = uuid4().hex
    name = f"izo-search-{run_id}-{attempt}-{owner}"
    previous = {item: signal.getsignal(item) for item in (signal.SIGINT, signal.SIGTERM)}
    for item in previous:
        signal.signal(item, cancel)
    result, created = 1, None
    try:
        container = docker("run", "--detach", "--rm", "--pull=never", "--name", name,
            "--label", f"{OWNER_LABEL}={owner}", "--publish", "127.0.0.1::5432",
            "--env", f"POSTGRES_USER={env['IZO_PG_USER']}",
            "--env", f"POSTGRES_DB={env['IZO_PG_DATABASE']}",
            "--env", f"POSTGRES_PASSWORD={env['IZO_PG_PASSWORD']}",
            "--health-cmd=pg_isready -h 127.0.0.1 -p 5432 -U " + env["IZO_PG_USER"]
            + " -d " + env["IZO_PG_DATABASE"], "--health-interval=1s", "--health-timeout=3s",
            "--health-retries=30", "postgres:17-bookworm").stdout.strip()
        if not re.fullmatch(r"[0-9a-f]{64}", container):
            raise RuntimeError("Docker did not return a full PostgreSQL container ID")
        created = container
        for _ in range(45):
            health = docker("inspect", "--format", "{{.State.Health.Status}}", container).stdout.strip()
            if health == "healthy":
                break
            if health == "unhealthy":
                raise RuntimeError("Isolated PostgreSQL became unhealthy")
            time.sleep(1)
        else:
            raise RuntimeError("Isolated PostgreSQL did not become healthy in 45 probes")
        binding = docker("port", container, "5432/tcp").stdout.strip()
        matched = re.fullmatch(r"127\.0\.0\.1:([0-9]+)", binding)
        if not matched or not 1 <= int(matched[1]) <= 65535:
            raise RuntimeError("PostgreSQL must publish one loopback-only port")
        env["IZO_PG_PORT"] = matched[1]
        completed = subprocess.run([sys.executable, "-B", "tests/test_chat_thread_search_postgres.py"],
                                   cwd=ROOT, env=env)
        result = completed.returncode
        if result < 0:
            result = 128 - result
    except SystemExit as error:
        result = int(error.code)
    except subprocess.CalledProcessError as error:
        print(error.stderr or "PostgreSQL CI command failed", file=sys.stderr)
        result = error.returncode if error.returncode > 0 else 128 - error.returncode
    except (OSError, RuntimeError) as error:
        print(f"PostgreSQL CI failed: {error}", file=sys.stderr)
    finally:
        # Repeated cancellation must not interrupt removal of our disposable container.
        for item in previous:
            signal.signal(item, signal.SIG_IGN)
        try:
            if not cleanup(name, owner, created):
                result = result or 1
        except OSError as error:
            print(f"PostgreSQL cleanup failed: {error}", file=sys.stderr)
            result = result or 1
        finally:
            for item, handler in previous.items():
                signal.signal(item, handler)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
