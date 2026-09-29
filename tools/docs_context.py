"""Low-token routing and local-document validation helpers for check_docs."""
from __future__ import annotations

import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
ROUTE_HARD_BYTES = 18_000
BLOCK_DOC_HARD_BYTES = 12_000
DEFAULT_READ_HARD_BYTES = 6_000
LOCAL_DOC_HARD_BYTES = 6_000


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path.relative_to(ROOT)} must contain an object")
    return value


def load_map(path: Path, section: str) -> tuple[dict, list[Path]]:
    value = load_json(path)
    sources = [path]
    shards = value.get("shards", [])
    if not shards:
        return value, sources
    if not isinstance(shards, list) or not all(isinstance(raw, str) and raw for raw in shards):
        raise ValueError(f"{path.relative_to(ROOT)} has invalid shards list")
    combined = dict(value.get(section, {}))
    for raw in shards:
        shard_path = ROOT / raw
        shard = load_json(shard_path)
        sources.append(shard_path)
        entries = shard.get(section, {})
        if not isinstance(entries, dict):
            raise ValueError(f"{raw} requires object section {section}")
        duplicate = combined.keys() & entries.keys()
        if duplicate:
            raise ValueError(f"duplicate {section} keys across shards: {sorted(duplicate)}")
        combined.update(entries)
    result = dict(value); result[section] = combined
    return result, sources


def paths_bytes(paths: list[str]) -> int:
    total = 0
    for raw in dict.fromkeys(paths):
        path = ROOT / raw
        if path.is_file():
            total += path.stat().st_size
    return total


def check_map_files(errors: list[str], label: str, sources: list[Path], hard_bytes: int) -> None:
    for path in sources:
        if path.stat().st_size > hard_bytes:
            errors.append(f"{label} shard/index exceeds {hard_bytes} bytes: {path.relative_to(ROOT)}")


def check_context(errors: list[str], context: dict, sources: list[Path]) -> None:
    check_map_files(errors, "CONTEXT_MAP", sources, 20_000)
    if context.get("schema_version") != 1:
        errors.append("CONTEXT_MAP schema_version must be 1")
    default_read = context.get("default_read", [])
    if paths_bytes(default_read) > DEFAULT_READ_HARD_BYTES:
        errors.append(f"default agent read exceeds {DEFAULT_READ_HARD_BYTES} bytes")
    routes = context.get("routes")
    if not isinstance(routes, dict) or not routes:
        errors.append("CONTEXT_MAP routes must be a non-empty object")
        return
    for rule in context.get("semantic_rules", []):
        if not isinstance(rule, dict) or not isinstance(rule.get("scores"), dict):
            errors.append("semantic routing rule requires an object with scores")
            continue
        unknown = set(rule["scores"]) - set(routes)
        if unknown:
            errors.append(f"semantic routing rule references unknown routes: {sorted(unknown)}")
    for key, route in routes.items():
        if not route.get("keywords") or not route.get("read_first"):
            errors.append(f"route {key} requires keywords/read_first")
        for field in ("read_first", "tests", "expand_if_needed", "do_not_read_by_default"):
            for raw in route.get(field, []):
                if not isinstance(raw, str) or not raw or not (ROOT / raw).exists():
                    errors.append(f"route {key}.{field} missing path: {raw}")
        initial = paths_bytes(route.get("read_first", []))
        if initial > ROUTE_HARD_BYTES:
            errors.append(f"route {key} initial context {initial} exceeds {ROUTE_HARD_BYTES} bytes")


def local_map(route: dict) -> str | None:
    for raw in route.get("read_first", []):
        if raw.endswith("README.md"):
            return raw
    return None


def check_blocks(errors: list[str], blocks: dict, context: dict, sources: list[Path]) -> None:
    check_map_files(errors, "BLOCK_MAP", sources, 30_000)
    if blocks.get("schema_version") != 1:
        errors.append("BLOCK_MAP schema_version must be 1")
    for key, block in blocks.get("blocks", {}).items():
        route = block.get("route")
        if route not in context.get("routes", {}):
            errors.append(f"block {key} references unknown route {route}")
            continue
        owner = ROOT / str(block.get("owner", ""))
        if not owner.is_file():
            errors.append(f"block {key} owner missing: {block.get('owner')}")
            continue
        anchor = block.get("anchor")
        if not isinstance(anchor, str) or not anchor or anchor not in owner.read_text(encoding="utf-8"):
            errors.append(f"block {key} anchor missing from owner: {anchor}")
        for raw in [*block.get("support", []), *block.get("tests", [])]:
            if not (ROOT / raw).exists():
                errors.append(f"block {key} path missing: {raw}")
        initial_docs = ["AGENTS.md", "docs/CURRENT.md"]
        mapping = local_map(context["routes"][route])
        if mapping:
            initial_docs.append(mapping)
        total = paths_bytes(initial_docs)
        if total > BLOCK_DOC_HARD_BYTES:
            errors.append(f"block {key} initial documentation {total} exceeds {BLOCK_DOC_HARD_BYTES} bytes")


def local_doc_groups() -> list[Path]:
    groups: list[Path] = []
    for base in (ROOT / "apps/api/izo", ROOT / "apps/web/src/features"):
        if base.exists():
            groups.extend(child for child in base.iterdir() if child.is_dir() and child.name != "__pycache__")
    return groups


def check_coverage(errors: list[str], context: dict) -> None:
    route_paths = {raw for route in context.get("routes", {}).values() for raw in route.get("read_first", [])}
    mutable_sha = re.compile(r"\b[0-9a-f]{40}\b")
    mutable_pr = re.compile(r"\bPR\s*#\d+\b", re.I)
    mutable_branch = re.compile(r"(?:рабочая\s+ветка|working\s+branch)\s*:", re.I)
    next_package = re.compile(r"следующ(?:ий|ая|ее).{0,40}пакет", re.I)
    lifecycle_drift = re.compile(r"(?:после\s+acceptance\s+продолжать|остаются\s+демо|для\s+этого\s+нужны\s+(?:CREDIT|MEDIA|JOBS))", re.I)
    for child in local_doc_groups():
        readme = child / "README.md"
        raw = readme.relative_to(ROOT).as_posix()
        if not readme.is_file():
            errors.append(f"local ownership README missing: {raw}")
        elif raw not in route_paths:
            errors.append(f"local ownership README is not covered by a context route: {raw}")
        live_docs = sorted(path for path in child.glob("*.md") if path.is_file())
        total = sum(path.stat().st_size for path in live_docs)
        if total > LOCAL_DOC_HARD_BYTES:
            errors.append(f"local live docs exceed {LOCAL_DOC_HARD_BYTES} bytes: {child.relative_to(ROOT)}={total}")
        for path in live_docs:
            text = path.read_text(encoding="utf-8")
            if (mutable_sha.search(text) or mutable_pr.search(text) or mutable_branch.search(text)
                    or next_package.search(text) or lifecycle_drift.search(text)):
                errors.append(f"local live doc contains mutable/history lifecycle language: {path.relative_to(ROOT)}")
