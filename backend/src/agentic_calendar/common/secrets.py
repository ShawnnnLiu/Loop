"""Symmetric encryption for secrets stored at rest (Fernet).

Per-user Google OAuth tokens are persisted in the shared SQLite database, so —
unlike the operator CLI's single ``.secrets/google_token.json`` (protected by
file permissions alone) — they must be encrypted before they touch a row. This
kernel wraps :class:`cryptography.fernet.Fernet` (authenticated AES-128-CBC +
HMAC) behind a tiny seam: the key comes from the environment, never the repo,
and ciphertext/plaintext never get logged.

``common`` is the one package every region may import, and ``cryptography`` is
not an LLM SDK, so this lives here without tripping a boundary contract. It is
deliberately *not* re-exported from ``common/__init__`` — importers ask for
``agentic_calendar.common.secrets`` explicitly so a plain ``import common``
does not drag in the crypto dependency.
"""

from __future__ import annotations

import os

from cryptography.fernet import Fernet, InvalidToken

from agentic_calendar.common.errors import AgenticCalendarError

DEFAULT_KEY_ENV_VAR = "APP_TOKEN_ENCRYPTION_KEY"


class TokenCipherError(AgenticCalendarError):
    """Encryption/decryption failed or the configured key is unusable."""


class TokenCipher:
    """Encrypt/decrypt secret strings (e.g. OAuth token JSON) with one key.

    The key is a url-safe base64-encoded 32-byte Fernet key. Generate one once
    with :meth:`generate_key` and supply it through the environment in every
    process that reads or writes tokens.
    """

    def __init__(self, key: str) -> None:
        try:
            self._fernet = Fernet(key.encode("utf-8"))
        except (ValueError, TypeError) as exc:
            # Wrong length / not base64: surface a typed error, never echo the key.
            raise TokenCipherError(
                "invalid Fernet key; generate one with TokenCipher.generate_key()"
            ) from exc

    @classmethod
    def from_env(cls, var: str = DEFAULT_KEY_ENV_VAR) -> TokenCipher:
        key = os.environ.get(var)
        if not key:
            raise TokenCipherError(
                f"{var} is not set; generate one with TokenCipher.generate_key() "
                "and export it (keep it out of version control)"
            )
        return cls(key)

    @staticmethod
    def generate_key() -> str:
        """A fresh url-safe base64 Fernet key, suitable for the env var."""
        return Fernet.generate_key().decode("utf-8")

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")

    def decrypt(self, ciphertext: str) -> str:
        try:
            return self._fernet.decrypt(ciphertext.encode("utf-8")).decode("utf-8")
        except InvalidToken as exc:
            raise TokenCipherError(
                "token could not be decrypted (wrong key or corrupted ciphertext)"
            ) from exc
