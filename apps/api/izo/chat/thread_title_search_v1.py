"""Versioned, server-owned title matching and opaque search cursor encoding."""
import base64
import binascii
import hashlib
import json
import re
import sys
import unicodedata
from uuid import UUID

MATCHER_VERSION = 1
JS_TRIM = "\u0009\u000a\u000b\u000c\u000d\u0020\u00a0\u1680"
JS_TRIM += "\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a"
JS_TRIM += "\u2028\u2029\u202f\u205f\u3000\ufeff"


def check_runtime() -> None:
    # Persisted keys and query keys must never silently use different Unicode data.
    if sys.version_info[:2] != (3, 13) or unicodedata.unidata_version != "15.1.0":
        raise RuntimeError("Title matcher v1 requires Python 3.13 / Unicode 15.1")


def title_key(title: str) -> str:
    check_runtime()
    return title.lower()


def query_key(value: str) -> str:
    if "\x00" in value or any(0xD800 <= ord(c) <= 0xDFFF for c in value):
        raise ValueError("invalid_input")
    return title_key(value.strip(JS_TRIM))


def _encoded(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _query_digest(query: str) -> str:
    return _encoded(hashlib.sha256(query.encode("utf-8")).digest())


def search_cursor(account_id: UUID, query: str, row) -> str:
    payload = {"v": 2, "m": MATCHER_VERSION, "a": account_id.hex,
               "q": _query_digest(query), "t": row["created_at"], "i": row["id"].hex}
    return _encoded(json.dumps(payload, separators=(",", ":")).encode("ascii"))


def search_boundary(cursor: str | None, account_id: UUID, query: str):
    if cursor is None:
        return None
    try:
        if len(cursor) > 256 or not re.fullmatch(r"[A-Za-z0-9_-]+", cursor):
            raise ValueError()
        payload = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
        if (not isinstance(payload, dict) or set(payload) != {"v", "m", "a", "q", "t", "i"}
                or type(payload["v"]) is not int or payload["v"] != 2
                or type(payload["m"]) is not int or payload["m"] != MATCHER_VERSION
                or payload["a"] != account_id.hex or payload["q"] != _query_digest(query)
                or type(payload["t"]) is not int or not 0 <= payload["t"] <= 2**63 - 1
                or not isinstance(payload["i"], str)
                or not re.fullmatch(r"[0-9a-f]{32}", payload["i"])):
            raise ValueError()
        return payload["t"], UUID(hex=payload["i"])
    except (ValueError, TypeError, KeyError, UnicodeError, binascii.Error):
        raise ValueError("invalid_thread_cursor") from None
