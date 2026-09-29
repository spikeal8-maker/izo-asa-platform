"""Bounded image rewrite in a disposable subprocess. No URLs, shell or SVG."""
import io
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import warnings
from dataclasses import dataclass
from threading import BoundedSemaphore

from .schemas import MAX_INPUT, MAX_OUTPUT, MAX_PIXELS, MediaError

FORMATS = {"image/png": "PNG", "image/jpeg": "JPEG", "image/webp": "WEBP"}
SLOTS = BoundedSemaphore(2)


@dataclass(frozen=True)
class CanonicalImage:
    data: bytes
    width: int
    height: int


class LimitedBuffer(io.BytesIO):
    def __init__(self, maximum):
        super().__init__()
        self.maximum = maximum

    def write(self, data):
        if self.tell() + len(data) > self.maximum:
            raise ValueError("output_limit")
        return super().write(data)


def rewrite(data, content_type, width, height, bound):
    """Only used in the child or unit tests; production calls decode()."""
    from PIL import Image, ImageOps, PngImagePlugin
    if not 0 < len(data) <= MAX_INPUT or not 0 < bound <= MAX_OUTPUT:
        raise ValueError("image_limit")
    Image.MAX_IMAGE_PIXELS = MAX_PIXELS
    PngImagePlugin.MAX_TEXT_CHUNK = 64 * 1024
    PngImagePlugin.MAX_TEXT_MEMORY = 256 * 1024
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        with Image.open(io.BytesIO(data), formats=list(FORMATS.values())) as check:
            if (check.format != FORMATS[content_type] or check.size != (width, height)
                    or width * height > MAX_PIXELS or getattr(check, "n_frames", 1) != 1):
                raise ValueError("image_mismatch")
            check.verify()
        with Image.open(io.BytesIO(data), formats=[FORMATS[content_type]]) as image:
            image.load()
            oriented = ImageOps.exif_transpose(image).convert("RGBA")
            # A fresh image removes ancillary data, EXIF, profiles and trailing
            # polyglot content. The stored object is NOT the original byte file.
            clean = Image.frombytes("RGBA", oriented.size, oriented.tobytes())
            output = LimitedBuffer(bound)
            clean.save(output, format="PNG", compress_level=3)
            result = CanonicalImage(output.getvalue(), clean.width, clean.height)
            clean.close()
            oriented.close()
            return result


def decode(data, content_type, width, height, bound):
    if not SLOTS.acquire(blocking=False):
        raise MediaError(429, "media_busy")
    try:
        completed = subprocess.run([sys.executable, "-m", "izo.media.codec"],
            input=json.dumps([content_type, width, height, bound]).encode() + b"\n" + data,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=20, check=False,
            env={"PATH": os.defpath, "PYTHONPATH": str(Path(__file__).resolve().parents[2]),
                 "PYTHONNOUSERSITE": "1", "AWS_EC2_METADATA_DISABLED": "true"})
        if completed.returncode != 0 or not 8 < len(completed.stdout) <= bound + 8:
            raise MediaError(422, "invalid_image")
        w, h = struct.unpack(">II", completed.stdout[:8])
        if (w, h) not in {(width, height), (height, width)} or not completed.stdout[8:].startswith(b"\x89PNG\r\n\x1a\n"):
            raise MediaError(422, "invalid_image")
        return CanonicalImage(completed.stdout[8:], w, h)
    except subprocess.TimeoutExpired:
        raise MediaError(422, "image_processing_limit") from None
    finally:
        SLOTS.release()


def main():
    # Linux server enforces child address-space and CPU limits. Other OSes retain
    # the wall-clock, input/output/pixel bounds; they are not a production sandbox.
    if sys.platform == "linux":
        import resource
        resource.setrlimit(resource.RLIMIT_AS, (512 * 1024**2, 512 * 1024**2))
        resource.setrlimit(resource.RLIMIT_CPU, (15, 15))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    try:
        args = json.loads(sys.stdin.buffer.readline(1024))
        data = sys.stdin.buffer.read(MAX_INPUT + 1)
        result = rewrite(data, *args)
        sys.stdout.buffer.write(struct.pack(">II", result.width, result.height) + result.data)
    except Exception:
        sys.exit(2)


if __name__ == "__main__":
    main()
