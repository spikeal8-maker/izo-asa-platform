"""Deterministic compressed OpenAPI snapshot consumed by openapi-typescript."""
import gzip
import hashlib
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
            # Temporary API-001 diagnostic. Existing CI uploads test-results on
            # failure; the file is public OpenAPI only, never secrets or user data.
            evidence = ROOT / "apps/web/test-results/openapi-canonical.json.gz"
            evidence.parent.mkdir(parents=True, exist_ok=True)
            evidence.write_bytes(expected)
            print("OPENAPI_CANONICAL_SHA256=" + hashlib.sha256(expected).hexdigest())
            raise SystemExit("OpenAPI changed: pinned snapshot saved to failure evidence")
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(expected)


if __name__ == "__main__":
    main()
