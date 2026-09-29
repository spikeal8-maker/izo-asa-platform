"""Versioned password hashing and independent high-entropy bearer/CSRF tokens."""
import hashlib
import hmac
import re
import secrets
from threading import BoundedSemaphore

TOKEN = re.compile(r"^[A-Za-z0-9_-]{43}$")
KDF_LIMIT = BoundedSemaphore(2)
# OWASP scrypt alternative: 32 MiB, r=8, p=3. No new crypto dependency.
N, R, P = 32768, 8, 3


class AuthError(Exception):
    def __init__(self, status: int, code: str, retry_after: int | None = None):
        super().__init__(code)
        self.status, self.code, self.retry_after = status, code, retry_after


def token() -> str:
    return secrets.token_urlsafe(32)


def token_hash(value: str) -> str:
    return hashlib.sha256(value.encode("ascii")).hexdigest()


def rate_key(secret: str, namespace: str, value: str) -> str:
    return hmac.new(secret.encode(), f"{namespace}:{value}".encode(), hashlib.sha256).hexdigest()


def derive(password: str, salt: bytes) -> bytes:
    if not KDF_LIMIT.acquire(timeout=0.1):
        raise AuthError(429, "auth_busy", 1)
    try:
        return hashlib.scrypt(password.encode("utf-8"), salt=salt, n=N, r=R, p=P,
                              dklen=32, maxmem=64 * 1024 * 1024)
    finally:
        KDF_LIMIT.release()


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = derive(password, salt)
    return f"scrypt-v1${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str | None) -> bool:
    # Unknown accounts still perform one full KDF; no expensive import-time hash.
    valid = False
    salt, expected = bytes(16), bytes(32)
    if encoded:
        parts = encoded.split("$")
        if len(parts) == 3 and parts[0] == "scrypt-v1":
            try:
                salt, expected = bytes.fromhex(parts[1]), bytes.fromhex(parts[2])
                valid = len(salt) == 16 and len(expected) == 32
            except ValueError:
                pass
    if not valid:
        salt, expected = bytes(16), bytes(32)
    return hmac.compare_digest(derive(password, salt), expected) and valid
