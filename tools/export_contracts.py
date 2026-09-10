"""Deterministic OpenAPI snapshot: gzip bytes stored as four reviewable base64 text parts."""
import base64
import gzip
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/api"))

from izo.app import create_app
from izo.config import Settings

PARTS = 4


def encoded() -> str:
    raw = (
        json.dumps(
            create_app(Settings()).openapi(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n"
    ).encode("utf-8")
    compressed = gzip.compress(raw, compresslevel=9, mtime=0)
    return base64.b64encode(compressed).decode("ascii")


def chunks(value: str) -> tuple[str, ...]:
    width = (len(value) + PARTS - 1) // PARTS
    return tuple(value[index * width:(index + 1) * width] for index in range(PARTS))


def targets() -> tuple[Path, ...]:
    base = ROOT / "packages/contracts/openapi.json.gz.b64"
    return tuple(Path(f"{base}.part{index}") for index in range(PARTS))


def main() -> None:
    expected = chunks(encoded())
    files = targets()
    if "--check" in sys.argv:
        if any(not path.exists() or path.read_text("ascii") != value
               for path, value in zip(files, expected, strict=True)):
            raise SystemExit("OpenAPI changed: run python tools/export_contracts.py in the pinned backend environment")
        return
    files[0].parent.mkdir(parents=True, exist_ok=True)
    for path, value in zip(files, expected, strict=True):
        path.write_text(value, encoding="ascii")


if __name__ == "__main__":
    main()
