"""Return the smallest documented context route for a maintenance request."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
MAP_PATH = ROOT / "docs" / "CONTEXT_MAP.json"


def load_map() -> dict:
    data = json.loads(MAP_PATH.read_text(encoding="utf-8"))
    if data.get("schema_version") != 1 or not isinstance(data.get("routes"), dict):
        raise ValueError("Unsupported CONTEXT_MAP schema")
    return data


def words(value: str) -> set[str]:
    return set(re.findall(r"[\w.-]+", value.casefold(), flags=re.UNICODE))


def score(task: str, route: dict) -> int:
    folded = task.casefold()
    task_words = words(task)
    total = 0
    for keyword in route.get("keywords", []):
        key = keyword.casefold().strip()
        if not key:
            continue
        if key in folded:
            total += 8 + len(words(key))
        else:
            overlap = len(task_words & words(key))
            total += overlap
    return total


def resolve(data: dict, task: str) -> tuple[str, dict]:
    ranked = sorted(((score(task, route), key, route) for key, route in data["routes"].items()), reverse=True)
    if not ranked or ranked[0][0] <= 0:
        raise LookupError("No documented context route matches this request")
    best = ranked[0]
    return best[1], best[2]

def render(key: str, route: dict) -> str:
    lines = [f"CONTEXT ROUTE: {key}", "READ FIRST:"]
    lines.extend(f"  - {path}" for path in route.get("read_first", []))
    tests = route.get("tests", [])
    if tests:
        lines.append("TARGETED TESTS:")
        lines.extend(f"  - {path}" for path in tests)
    expand = route.get("expand_if_needed", [])
    if expand:
        lines.append("EXPAND ONLY IF NEEDED:")
        lines.extend(f"  - {path}" for path in expand)
    blocked = route.get("do_not_read_by_default", [])
    if blocked:
        lines.append("DO NOT READ BY DEFAULT:")
        lines.extend(f"  - {path}" for path in blocked)
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--task", help="Natural-language maintenance request")
    group.add_argument("--key", help="Exact context route key")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()
    try:
        data = load_map()
        if args.key:
            if args.key not in data["routes"]:
                raise LookupError(f"Unknown context route: {args.key}")
            key, route = args.key, data["routes"][args.key]
        else:
            key, route = resolve(data, args.task)
        if args.as_json:
            print(json.dumps({"route": key, **route}, ensure_ascii=False, indent=2))
        else:
            print(render(key, route))
        return 0
    except (ValueError, OSError, json.JSONDecodeError, LookupError) as exc:
        print(f"CONTEXT NOT RESOLVED: {exc}", file=sys.stderr)
        print("Fallback: read docs/INDEX.md and search an exact visible text/route/symbol/error before widening context.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
