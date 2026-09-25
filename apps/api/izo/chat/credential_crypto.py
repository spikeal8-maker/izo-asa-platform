"""Provider-aware AES-GCM helpers for Chat credentials."""
import hashlib
import hmac
import os
from uuid import UUID

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def aad(
        account_id: UUID, connection_id: UUID, generation: int,
        provider: str = "deepseek") -> bytes:
    # Preserve the exact legacy DeepSeek AAD so existing ciphertext remains valid.
    if provider == "deepseek":
        value = f"izo-chat|deepseek|{account_id}|{connection_id}|{generation}"
    else:
        value = f"izo-chat|provider:{provider}|{account_id}|{connection_id}|{generation}"
    return value.encode("ascii")


def encrypt(
        root_key: bytes, account_id: UUID, connection_id: UUID,
        generation: int, plaintext: str, provider: str = "deepseek",
) -> tuple[bytes, bytes]:
    nonce = os.urandom(12)
    ciphertext = AESGCM(root_key).encrypt(
        nonce, plaintext.encode("utf-8"),
        aad(account_id, connection_id, generation, provider))
    return nonce, ciphertext


def decrypt(
        root_key: bytes, account_id: UUID, connection_id: UUID,
        generation: int, nonce: bytes, ciphertext: bytes,
        provider: str = "deepseek",
) -> str:
    value = AESGCM(root_key).decrypt(
        nonce, ciphertext,
        aad(account_id, connection_id, generation, provider))
    return value.decode("utf-8")


def operation_fingerprint(root_key: bytes, action: str, payload: bytes) -> str:
    return hmac.new(
        root_key, action.encode("ascii") + b"\0" + payload,
        hashlib.sha256).hexdigest()
