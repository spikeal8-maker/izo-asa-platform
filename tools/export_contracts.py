"""Deterministic compact OpenAPI snapshot consumed by openapi-typescript."""
import base64
import gzip
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/api"))
from izo.app import create_app
from izo.config import Settings


def content() -> str:
    raw = (json.dumps(create_app(Settings()).openapi(), ensure_ascii=False,
                      sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    encoded = base64.b64encode(gzip.compress(raw, compresslevel=9, mtime=0)).decode("ascii")
    return "\n".join(encoded[i:i + 76] for i in range(0, len(encoded), 76)) + "\n"


def main() -> None:
    target = ROOT / "packages/contracts/openapi.json.gz.b64"
    expected = content()
    if "--check" in sys.argv:
        if not target.exists() or target.read_text(encoding="ascii") != expected:
            raise SystemExit("OpenAPI changed: run python tools/export_contracts.py")
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(expected, encoding="ascii", newline="\n")


if __name__ == "__main__":
    main()
