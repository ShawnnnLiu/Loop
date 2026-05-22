"""Deterministic identifier generation.

Identifiers (`run_id`, `plan_version`, `task_id`, etc.) cross every region of
the system; they appear in logs, telemetry, calendar mappings, and approval
events. Generators are injectable so tests can pin sequences and replay.

For Phase 1 we only need a couple of generator shapes:

* ``IdGenerator`` — produces opaque, monotonic-ish IDs from a prefix.
* ``DeterministicIdGenerator`` — counter-based; used in tests.

Real production wiring will use a UUID-backed implementation that lives here
as ``UuidIdGenerator``; nothing else needs to change when we swap.
"""

from __future__ import annotations

import threading
import uuid
from typing import Protocol, runtime_checkable


@runtime_checkable
class IdGenerator(Protocol):
    """Generate stable, prefixed identifiers."""

    def new_id(self, prefix: str) -> str:
        """Return a new identifier of the form ``"<prefix>_<token>"``."""
        ...


class UuidIdGenerator:
    """Production generator backed by a short UUID4 hex slice."""

    def __init__(self, *, hex_chars: int = 12) -> None:
        if hex_chars < 4 or hex_chars > 32:
            raise ValueError("hex_chars must be between 4 and 32")
        self._hex_chars = hex_chars

    def new_id(self, prefix: str) -> str:
        if not prefix:
            raise ValueError("prefix must be non-empty")
        return f"{prefix}_{uuid.uuid4().hex[: self._hex_chars]}"


class DeterministicIdGenerator:
    """Counter-based generator for tests; thread-safe.

    Each prefix gets its own monotonic counter starting at 1, formatted
    zero-padded to ``digits`` (default 3). Two instances produce identical
    sequences when called in the same order, so test fixtures stay stable
    across runs.
    """

    def __init__(self, *, digits: int = 3) -> None:
        if digits < 1 or digits > 10:
            raise ValueError("digits must be between 1 and 10")
        self._digits = digits
        self._counters: dict[str, int] = {}
        self._lock = threading.Lock()

    def new_id(self, prefix: str) -> str:
        if not prefix:
            raise ValueError("prefix must be non-empty")
        with self._lock:
            n = self._counters.get(prefix, 0) + 1
            self._counters[prefix] = n
        return f"{prefix}_{n:0{self._digits}d}"
