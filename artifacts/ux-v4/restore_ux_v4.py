#!/usr/bin/env python3
from base64 import b64decode
from hashlib import sha256
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parent
PARTS = sorted((ROOT / "archive").glob("IZO_ASA_UX_SPEC_V4.tar.xz.b64.part*"))
EXPECTED_PARTS = 9
EXPECTED_SHA256 = "ed4dfc898f589d4e81d3d2eb1d53086ccb0fec1ccb06a9a4126b23bbad7a3897"
EXPECTED_TOP_LEVEL = "IZO_ASA_UX_SPEC_V4"

if len(PARTS) != EXPECTED_PARTS:
    raise SystemExit(f"expected {EXPECTED_PARTS} parts, found {len(PARTS)}")

encoded = "".join(part.read_text(encoding="ascii") for part in PARTS)
archive_bytes = b64decode(encoded, validate=True)
actual = sha256(archive_bytes).hexdigest()
if actual != EXPECTED_SHA256:
    raise SystemExit(f"archive checksum mismatch: {actual}")

archive = ROOT / "IZO_ASA_UX_SPEC_V4.tar.xz"
archive.write_bytes(archive_bytes)
with tarfile.open(archive, mode="r:xz") as tf:
    members = tf.getmembers()
    for member in members:
        path = Path(member.name)
        if path.is_absolute() or ".." in path.parts or not path.parts or path.parts[0] != EXPECTED_TOP_LEVEL:
            raise SystemExit(f"unsafe archive member: {member.name}")
    tf.extractall(ROOT, members=members, filter="data")

print(f"restored {archive.name}; sha256={actual}; members={len(members)}")
