"""Tests for :class:`agentic_calendar.common.secrets.TokenCipher`."""

from __future__ import annotations

import pytest

from agentic_calendar.common.secrets import TokenCipher, TokenCipherError

SECRET = '{"token": "abc", "refresh_token": "xyz"}'


def test_round_trip() -> None:
    cipher = TokenCipher(TokenCipher.generate_key())
    ciphertext = cipher.encrypt(SECRET)
    assert ciphertext != SECRET
    assert cipher.decrypt(ciphertext) == SECRET


def test_ciphertext_is_nondeterministic() -> None:
    # Fernet uses a random IV, so the same plaintext encrypts differently.
    cipher = TokenCipher(TokenCipher.generate_key())
    a, b = cipher.encrypt("same"), cipher.encrypt("same")
    assert a != b
    assert cipher.decrypt(a) == cipher.decrypt(b) == "same"


def test_wrong_key_cannot_decrypt() -> None:
    ciphertext = TokenCipher(TokenCipher.generate_key()).encrypt(SECRET)
    with pytest.raises(TokenCipherError):
        TokenCipher(TokenCipher.generate_key()).decrypt(ciphertext)


def test_corrupted_ciphertext_rejected() -> None:
    cipher = TokenCipher(TokenCipher.generate_key())
    with pytest.raises(TokenCipherError):
        cipher.decrypt("not-valid-ciphertext")


def test_invalid_key_rejected() -> None:
    with pytest.raises(TokenCipherError):
        TokenCipher("not-a-valid-fernet-key")


def test_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_TOKEN_ENCRYPTION_KEY", TokenCipher.generate_key())
    cipher = TokenCipher.from_env()
    assert cipher.decrypt(cipher.encrypt("x")) == "x"


def test_from_env_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("APP_TOKEN_ENCRYPTION_KEY", raising=False)
    with pytest.raises(TokenCipherError):
        TokenCipher.from_env()
