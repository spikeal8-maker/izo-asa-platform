"""Authenticated encryption boundary for account-owned provider keys."""
from __future__ import annotations

import hashlib
import hmac
import os
from uuid import UUID

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

def aad(account_id: UUID, connection_id: UUID, generation: int) -> bytes:
    return f"izo-chat|deepseek|{account_id}|{connection_id}|{generation}".encode("ascii")

def encrypt(root_key: bytes, account_id: UUID, connection_id: UUID,
            generation: int, plaintext: str) -> tuple[bytes, bytes]:
    nonce = os.urandom(12)
    ciphertext = AESGCM(root_key).encrypt(
        nonce, plaintext.encode("utf-8"), aad(account_id, connection_id, generation))
    return nonce, ciphertext

def decrypt(root_key: bytes, account_id: UUID, connection_id: UUID,
            generation: int, nonce: bytes, ciphertext: bytes) -> str:
    value = AESGCM(root_key).decrypt(
        nonce, ciphertext, aad(account_id, connection_id, generation))
    return value.decode("utf-8")

def operation_fingerprint(root_key: bytes, action: str, payload: bytes) -> str:
    return hmac.new(root_key, action.encode("ascii") + b"\0" + payload,
                    hashlib.sha256).hexdigest()
