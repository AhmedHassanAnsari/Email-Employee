"""Symmetric encryption for refresh tokens at rest (Fernet).

The key comes from ``TOKEN_ENCRYPTION_KEY`` (a urlsafe-base64 32-byte Fernet
key). Generate one with:

    uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

We never store a Google refresh token in plaintext — ``encrypt`` before writing
to ``google_tokens.refresh_token_enc`` and ``decrypt`` when minting a token.
"""

from __future__ import annotations

import os
from functools import lru_cache

from cryptography.fernet import Fernet


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    key = os.environ.get("TOKEN_ENCRYPTION_KEY")
    if not key:
        raise RuntimeError(
            "TOKEN_ENCRYPTION_KEY is not set — generate one with "
            "Fernet.generate_key() and add it to .env"
        )
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt(ciphertext: str) -> str:
    return _fernet().decrypt(ciphertext.encode()).decode()
