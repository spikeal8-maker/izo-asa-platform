"""Windows acceptance for local Chat preview config and root-key guard."""
from __future__ import annotations
import base64
import os
import subprocess as sp
import tempfile
from pathlib import Path
import build_preview

def main() -> None:
    script = build_preview.start_cmd()
    guard = "docker volume inspect izo-chat-preview_postgres-data"
    generation = "New-Base64Secret 32"
    assert guard in script and "No new key was generated" in script
    assert script.index(guard) < script.index(generation)
    with tempfile.TemporaryDirectory(prefix="izo-chat-bootstrap-") as directory:
        root = Path(directory)
        (root / "start.cmd").write_text(script, encoding="utf-8", newline="\r\n")
        command = ["cmd", "/d", "/c", "start.cmd", "--check-config"]
        sp.run(command, cwd=root, check=True)
        first = (root / ".env").read_bytes()
        values = dict(line.split("=", 1) for line in first.decode("ascii").splitlines())
        key = values["IZO_CHAT_ROOT_KEY"]
        assert len(values) == 12
        assert values["IZO_CHAT_LOCAL_PREVIEW_ENABLED"] == "true"
        decoded = base64.urlsafe_b64decode(key + "=")
        assert len(decoded) == 32 and decoded != b"\0" * 32
        sp.run(command, cwd=root, check=True)
        assert (root / ".env").read_bytes() == first
        old = "\n".join(line for line in first.decode("ascii").splitlines()
                        if not line.startswith("IZO_CHAT_LOCAL_PREVIEW_ENABLED=")) + "\n"
        (root / ".env").write_text(old, encoding="ascii")
        sp.run(command, cwd=root, check=True)
        upgraded = dict(line.split("=", 1) for line in
                        (root / ".env").read_text(encoding="ascii").splitlines())
        assert upgraded["IZO_CHAT_ROOT_KEY"] == key
        assert upgraded["IZO_CHAT_LOCAL_PREVIEW_ENABLED"] == "true"
        (root / ".env").unlink()
        (root / "docker.cmd").write_text("@echo off\r\nexit /b 0\r\n", encoding="ascii")
        env = os.environ.copy()
        env["PATH"] = str(root) + os.pathsep + env["PATH"]
        stopped = sp.run(["cmd", "/d", "/c", "call", "start.cmd"],
                         cwd=root, env=env, capture_output=True, text=True)
        assert stopped.returncode == 2 and not (root / ".env").exists()
        assert "No new key was generated" in stopped.stdout
    print("WINDOWS_PREVIEW_GUARD_OK; ROOT_PRESERVED; LOST_ENV_DB_GUARD_EXECUTED")

if __name__ == "__main__":
    main()

