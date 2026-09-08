"""Deterministic OpenAPI export consumed by openapi-typescript; never starts services."""
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/api"))
from izo.app import create_app
from izo.config import Settings


def main() -> None:
    target = ROOT / "packages/contracts/openapi.json"
    content = json.dumps(create_app(Settings()).openapi(), ensure_ascii=False,
                         indent=2, sort_keys=True) + "\n"
    if "--check" in sys.argv:
        if not target.exists() or target.read_text(encoding="utf-8") != content:
            raise SystemExit("OpenAPI changed: run python tools/export_contracts.py")
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    main()
