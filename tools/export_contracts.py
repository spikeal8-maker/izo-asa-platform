"""Deterministic compressed OpenAPI snapshot consumed by openapi-typescript."""
import base64
import gzip
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/api"))
from izo.app import create_app
from izo.config import Settings


def content() -> bytes:
    raw = (json.dumps(create_app(Settings()).openapi(), ensure_ascii=False,
                      sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    return gzip.compress(raw, compresslevel=9, mtime=0)


def main() -> None:
    target = ROOT / "packages/contracts/openapi.json.gz"
    expected = content()
    if "--check" in sys.argv:
        if not target.exists() or target.read_bytes() != expected:
            # Temporary API-001 diagnostic: the pinned CI runtime is the canonical
            # generator. This contains public OpenAPI only, no secrets or data.
            print("OPENAPI_GZIP_BASE64=" + base64.b64encode(expected).decode("ascii"))
            raise SystemExit("OpenAPI changed: canonical pinned snapshot printed above")
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(expected)


if __name__ == "__main__":
    main()
