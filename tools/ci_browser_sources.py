"""Disable only dedicated Chrome feeds on a disposable CI runner.

Playwright downloads its own Chromium. Never alter Ubuntu repositories, keys,
APT authentication settings or an unrelated/mixed source. Support both APT
formats; a fixed google-chrome.list filename misses Deb822 .sources entries.
"""
from pathlib import Path
import os
import re

CHROME_URI = re.compile(r"https?://dl\.google\.com/linux/chrome(?:-stable)?/deb/?")
LIST_ENTRY = re.compile(
    r"deb(?:-src)?(?:\s+\[[^]\r\n]+\])?\s+"
    r"https?://dl\.google\.com/linux/chrome(?:-stable)?/deb/?\s+stable\s+main"
)


def chrome_only_sources(text: str) -> bool:
    """Recognize a dedicated Deb822 feed; unsupported/mixed content fails closed."""
    paragraphs: list[dict[str, str]] = []
    fields: dict[str, str] = {}
    previous = ""
    for line in text.splitlines() + [""]:
        if not line.strip():
            if fields:
                paragraphs.append(fields)
            fields, previous = {}, ""
        elif line.lstrip().startswith("#"):
            continue
        elif line[0].isspace():
            if not previous:
                return False
            fields[previous] += " " + line.strip()
        else:
            key, separator, value = line.partition(":")
            key = key.lower()
            if not separator or not re.fullmatch(r"[a-z][a-z0-9-]*", key) or key in fields:
                return False
            fields[key], previous = value.strip(), key
    if not paragraphs:
        return False
    for fields in paragraphs:
        uris = fields.get("uris", "").split()
        types = fields.get("types", "").split()
        if (not uris or not all(CHROME_URI.fullmatch(uri) for uri in uris)
                or not types or not set(types) <= {"deb", "deb-src"}
                or fields.get("suites", "").split() != ["stable"]
                or fields.get("components", "").split() != ["main"]
                or fields.get("enabled", "yes").lower() not in {"yes", "no"}):
            return False
    return True


def disable_unused_chrome(root: Path) -> tuple[str, ...]:
    """Validate the entire rename plan first; preserve original bytes in backups."""
    if root.is_symlink() or not root.is_dir():
        raise RuntimeError("Unexpected APT source directory")
    sources = sorted([*root.glob("*.list"), *root.glob("*.sources")])
    if len(sources) > 256:
        raise RuntimeError("Unexpected APT source count")
    plan: list[tuple[Path, Path]] = []
    for source in sources:
        if source.is_symlink() or not source.is_file():
            raise RuntimeError("Unexpected APT source symlink or non-file")
        if source.stat().st_size > 131072:
            raise RuntimeError("Unexpected APT source size")
        text = source.read_text(encoding="utf-8")
        if "chrome" not in source.name.lower() and "dl.google.com/linux/chrome" not in text:
            continue
        if source.suffix == ".list":
            active = [line.split("#", 1)[0].strip() for line in text.splitlines()]
            active = [line for line in active if line]
            valid = bool(active) and all(LIST_ENTRY.fullmatch(line) for line in active)
        else:
            valid = chrome_only_sources(text)
        if not valid:
            raise RuntimeError("Unexpected Chrome source contents; nothing disabled")
        destination = source.with_suffix(source.suffix + ".izo-disabled")
        if destination.exists() or destination.is_symlink():
            raise RuntimeError("Chrome source backup already exists")
        plan.append((source, destination))
    for source, destination in plan:
        source.rename(destination)
    names = tuple(source.name for source, _ in plan)
    print(f"CI_BROWSER_SOURCES: inspected={len(sources)} disabled={len(names)} files={','.join(names)}")
    return names


if __name__ == "__main__":
    if os.environ.get("IZO_CI_BROWSER_SETUP") != "isolated":
        raise SystemExit("Explicit isolated CI setup is required")
    disable_unused_chrome(Path("/etc/apt/sources.list.d"))
