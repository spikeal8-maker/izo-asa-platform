"""Resolve a maintenance request to the smallest safe documented context."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
MAP_PATH = ROOT / "docs" / "CONTEXT_MAP.json"
BLOCK_PATH = ROOT / "docs" / "BLOCK_MAP.json"
UI_HINTS = ("кноп", "цвет", "шир", "отступ", "текст", "надпис", "икон", "css", "layout", "button", "label", "визуал")
BACKEND_HINTS = ("backend", "api", "сервер", "списан", "резерв", "refund", "retry", "request_id", "permission", "quota", "worker", "provider", "fal")
GENERIC_STEMS = ("кноп", "сдел", "измен", "помен", "правк", "текст", "шир", "цвет", "button", "change", "fix", "backend", "api", "job")


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise ValueError(f"Unsupported schema: {path.name}")
    return value


def words(value: str) -> set[str]:
    return set(re.findall(r"[\w.-]+", value.casefold(), flags=re.UNICODE))


def content_words(value: str) -> set[str]:
    return {word for word in words(value) if not any(word.startswith(stem) for stem in GENERIC_STEMS)}


def phrase_score(task: str, phrases: list[str]) -> int:
    folded, task_words = task.casefold(), content_words(task)
    total = 0
    for raw in phrases:
        phrase = raw.casefold().strip()
        if not phrase:
            continue
        if phrase in folded:
            total += 12 + 2 * len(words(phrase))
        else:
            total += len(task_words & content_words(phrase))
    return total


def intent_bonus(task: str, kind_or_key: str) -> int:
    folded = task.casefold()
    ui = any(token in folded for token in UI_HINTS)
    backend = any(token in folded for token in BACKEND_HINTS)
    is_ui = kind_or_key.startswith("ui") or kind_or_key.startswith("web.")
    is_backend = kind_or_key.startswith("backend") or kind_or_key.startswith("api.")
    bonus = 0
    if ui and is_ui:
        bonus += 5
    if backend and is_backend:
        bonus += 5
    if ui and is_backend:
        bonus -= 2
    if backend and is_ui:
        bonus -= 2
    return bonus


def rank(task: str, items: dict, phrase_field: str) -> list[tuple[int, str, dict]]:
    ranked = []
    for key, item in items.items():
        score = phrase_score(task, item.get(phrase_field, []))
        if score > 0:
            score += intent_bonus(task, item.get("kind", key))
        ranked.append((score, key, item))
    return sorted(ranked, key=lambda value: (value[0], value[1]), reverse=True)


def choose(ranked: list[tuple[int, str, dict]], *, min_confident: int = 1) -> tuple[str, dict, int, int]:
    if not ranked or ranked[0][0] <= 0:
        raise LookupError("No documented context matches this request")
    top = ranked[0]
    second_score = ranked[1][0] if len(ranked) > 1 else 0
    ambiguous = second_score > 0 and (top[0] - second_score <= 2 or second_score / top[0] >= 0.82)
    if ambiguous:
        names = ", ".join(f"{key}={score}" for score, key, _ in ranked[:3] if score > 0)
        raise RuntimeError(f"AMBIGUOUS: {names}")
    if top[0] < min_confident:
        raise LookupError("No high-confidence block matches this request")
    return top[1], top[2], top[0], second_score


def local_map(route: dict) -> str | None:
    for path in route.get("read_first", []):
        if path.endswith("README.md"):
            return path
    return None


def file_bytes(paths: list[str]) -> int:
    total = 0
    for raw in dict.fromkeys(paths):
        path = ROOT / raw
        if path.is_file():
            total += path.stat().st_size
    return total


def render_block(key: str, block: dict, route: dict, score: int, second: int) -> str:
    read = ["AGENTS.md", "docs/CURRENT.md"]
    mapping = local_map(route)
    if mapping:
        read.append(mapping)
    lines = [
        f"CONTEXT BLOCK: {key}",
        f"CONFIDENCE: score={score} second={second}",
        f"OWNER: {block['owner']}",
        f"SYMBOL: {block['symbol']}",
        f"ANCHOR: {block['anchor']}",
        "READ FIRST:",
    ]
    lines.extend(f"  - {path}" for path in read)
    lines.append("SOURCE ACTION: search OWNER for ANCHOR/SYMBOL and read only the surrounding block, not the whole file.")
    if block.get("support"):
        lines.append("EXPAND ONLY IF NEEDED:")
        lines.extend(f"  - {path}" for path in block["support"])
    lines.append("TARGETED TESTS:")
    lines.extend(f"  - {path}" for path in block.get("tests", []))
    lines.append(f"INITIAL DOCUMENT BYTES: {file_bytes(read)}")
    return "\n".join(lines)


def render_route(key: str, route: dict, score: int, second: int) -> str:
    lines = [f"CONTEXT ROUTE: {key}", f"CONFIDENCE: score={score} second={second}", "READ FIRST:"]
    lines.extend(f"  - {path}" for path in route.get("read_first", []))
    if route.get("tests"):
        lines.append("TARGETED TESTS:")
        lines.extend(f"  - {path}" for path in route["tests"])
    if route.get("expand_if_needed"):
        lines.append("EXPAND ONLY IF NEEDED:")
        lines.extend(f"  - {path}" for path in route["expand_if_needed"])
    lines.append(f"INITIAL ROUTE BYTES: {file_bytes(route.get('read_first', []))}")
    return "\n".join(lines)


def resolve_task(task: str) -> tuple[str, str, dict, dict, int, int]:
    context = load_json(MAP_PATH)
    blocks = load_json(BLOCK_PATH)
    block_ranked = rank(task, blocks.get("blocks", {}), "aliases")
    try:
        key, block, score, second = choose(block_ranked, min_confident=7)
        route = context["routes"][block["route"]]
        return "block", key, block, route, score, second
    except LookupError:
        pass
    route_ranked = rank(task, context.get("routes", {}), "keywords")
    key, route, score, second = choose(route_ranked)
    return "route", key, route, route, score, second


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--task", help="Natural-language maintenance request")
    group.add_argument("--key", help="Exact route or block key")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()
    try:
        context = load_json(MAP_PATH)
        blocks = load_json(BLOCK_PATH)
        if args.key:
            if args.key in blocks.get("blocks", {}):
                item = blocks["blocks"][args.key]
                route = context["routes"][item["route"]]
                kind, key, score, second = "block", args.key, 0, 0
            elif args.key in context.get("routes", {}):
                item = route = context["routes"][args.key]
                kind, key, score, second = "route", args.key, 0, 0
            else:
                raise LookupError(f"Unknown context key: {args.key}")
        else:
            kind, key, item, route, score, second = resolve_task(args.task)
        if args.as_json:
            print(json.dumps({"kind": kind, "key": key, "score": score, "second_score": second, "item": item}, ensure_ascii=False, indent=2))
        elif kind == "block":
            print(render_block(key, item, route, score, second))
        else:
            print(render_route(key, route, score, second))
        return 0
    except RuntimeError as exc:
        print(f"CONTEXT AMBIGUOUS: {exc}", file=sys.stderr)
        print("Fallback: search exact visible text/symbol/API path before widening context.", file=sys.stderr)
        return 3
    except (ValueError, OSError, json.JSONDecodeError, LookupError) as exc:
        print(f"CONTEXT NOT RESOLVED: {exc}", file=sys.stderr)
        print("Fallback: read docs/INDEX.md and search exact visible text/route/symbol/error before widening context.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
