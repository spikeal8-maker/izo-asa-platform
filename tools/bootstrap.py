"""Create local development credentials once, never overwrite or print them."""
import argparse
import os
import re
import secrets
from pathlib import Path


def bootstrap(path: Path = Path(".env")) -> bool:
    values = {"IZO_ENVIRONMENT": "development", "IZO_PG_PASSWORD": secrets.token_hex(24),
              "IZO_S3_ACCESS_KEY": "izo" + secrets.token_hex(8),
              "IZO_S3_SECRET_KEY": secrets.token_hex(32), "IZO_HTTP_PORT": "8080",
              "IZO_AUTH_RATE_SECRET": secrets.token_hex(32), "IZO_AUTH_REGISTRATION": "invite",
              "IZO_RECOVERY_SECRET": secrets.token_hex(32), "IZO_RECOVERY_DELIVERY": "test"}
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return False
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as out:
        out.write("# Local development only. Never commit or publish this file.\n")
        out.write("".join(f"{key}={value}\n" for key, value in values.items()))
    return True


def _append_missing(path: Path, values: dict[str, str]) -> bool:
    """Explicit local upgrade; preserve every pre-existing value, even disabled."""
    if path.is_symlink():
        raise ValueError("Refusing a symlink environment file")
    before = path.read_text(encoding="utf-8")
    present = set(re.findall(r"^\s*(?:export\s+)?([A-Z][A-Z0-9_]*)\s*=", before, re.MULTILINE))
    missing = [(key, value) for key, value in values.items() if key not in present]
    if not missing:
        return False
    flags = os.O_WRONLY | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0)
    with os.fdopen(os.open(path, flags), "w", encoding="utf-8", newline="\n") as out:
        out.write(("\n" if not before.endswith("\n") else "") +
                  "".join(f"{key}={value}\n" for key, value in missing))
    return True


def add_auth_settings(path: Path = Path(".env")) -> bool:
    return _append_missing(path, {"IZO_AUTH_RATE_SECRET": secrets.token_hex(32), "IZO_AUTH_REGISTRATION": "invite"})


def add_recovery_settings(path: Path = Path(".env")) -> bool:
    return _append_missing(path, {"IZO_RECOVERY_SECRET": secrets.token_hex(32), "IZO_RECOVERY_DELIVERY": "test"})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--auth-only", action="store_true")
    group.add_argument("--recovery-only", action="store_true")
    args = parser.parse_args()
    changed = add_auth_settings() if args.auth_only else add_recovery_settings() if args.recovery_only else bootstrap()
    print("Local configuration added; values not displayed" if changed else "Existing .env preserved")
