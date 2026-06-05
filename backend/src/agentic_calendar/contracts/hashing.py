"""Canonical payload hashing for approval events.

Spec: ``docs/axioms/06-calendar-safety.md`` lines 139-198,
``docs/specs/approval-event.schema.md``, ``docs/specs/draft-schedule.schema.md``.

The Calendar Write Manager re-computes the payload hash at write time and
compares it to the recorded ``approved_payload_hash`` (axiom 06 lines 181-189).
A mismatch is a P1 incident; the write is aborted and the user must re-approve.

Hashing lives in ``contracts/`` rather than ``common/`` because it operates on
:class:`DraftSchedule` — a contract — and would otherwise force a
``common → contracts`` dependency that inverts the current leaf relationship.

Canonicalization is **versioned**. The ``hash_canonicalization_version``
recorded on each :class:`ApprovalEvent` selects the canonicalizer used to
recompute the hash at write time, so the algorithm can evolve without
invalidating prior approvals.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from typing import Any

from agentic_calendar.common.errors import AgenticCalendarError

from .draft_schedule import DraftSchedule

HashCanonicalizer = Callable[[DraftSchedule], bytes]


class UnsupportedCanonicalizationVersionError(AgenticCalendarError):
    """Raised when a caller asks for a canonicalization version not in the registry.

    The Calendar Write Manager catches this and surfaces
    ``ReasonCode.APPROVAL_HASH_ALGORITHM_UNSUPPORTED`` to the caller.
    """


_REGISTRY: dict[str, HashCanonicalizer] = {}


def register_canonicalizer(version: str, fn: HashCanonicalizer) -> None:
    """Register a canonicalizer for ``version``. Idempotent for the same function."""
    if not version:
        raise ValueError("canonicalization version must be non-empty")
    existing = _REGISTRY.get(version)
    if existing is not None and existing is not fn:
        raise ValueError(
            f"canonicalization version {version!r} already registered to a different function"
        )
    _REGISTRY[version] = fn


def get_canonicalizer(version: str) -> HashCanonicalizer:
    """Return the canonicalizer for ``version`` or raise.

    Raises:
        UnsupportedCanonicalizationVersionError: ``version`` is not registered.
    """
    fn = _REGISTRY.get(version)
    if fn is None:
        raise UnsupportedCanonicalizationVersionError(version)
    return fn


def canonical_payload_hash(draft: DraftSchedule, version: str = "v1") -> str:
    """Return ``"sha256:<64-hex>"`` for ``draft`` under ``version``.

    The only algorithm supported in the MVP is sha256 (axiom 06 line 165).
    """
    canonicalizer = get_canonicalizer(version)
    payload = canonicalizer(draft)
    digest = hashlib.sha256(payload).hexdigest()
    return f"sha256:{digest}"


def verify_payload_hash(
    draft: DraftSchedule, expected_hash: str, version: str
) -> bool:
    """Return True if recomputing the hash under ``version`` equals ``expected_hash``."""
    return canonical_payload_hash(draft, version) == expected_hash


def canonical_mapping_hash(payload: Mapping[str, Any], version: str = "v1") -> str:
    """Return ``"sha256:<64-hex>"`` for an arbitrary JSON-serializable mapping.

    Generalises the v1 canonicalization recipe (sorted keys, no whitespace) used
    by :func:`canonical_payload_hash` to any mapping, so callers such as the
    cache derive byte-stable keys without inventing their own hash. The payload
    must be JSON-serializable; only ``v1`` is supported in the MVP.
    """
    if version != "v1":
        raise UnsupportedCanonicalizationVersionError(version)
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(blob).hexdigest()}"


def _canonicalize_v1(draft: DraftSchedule) -> bytes:
    """v1 canonicalization (axiom 06 line 165: sorted keys, no whitespace).

    Covers exactly the fields axiom 06 lines 151-158 specify:
    ``draft_schedule_id``, ``plan_version``, ordered ``entries[*]`` of
    ``task_id``/``start``/``end``/``calendar_event_status``. Entries preserve
    the draft's order (the spec's "scheduled order"). Datetimes are emitted as
    ISO 8601 to preserve timezone.

    UI metadata, ``repair_options``, ``available_capacity_min``, and any other
    diagnostic field is excluded by construction — :class:`DraftSchedule`
    doesn't carry those.
    """
    payload = {
        "draft_schedule_id": draft.draft_schedule_id,
        "plan_version": draft.plan_version,
        "entries": [
            {
                "task_id": entry.task_id,
                "start": entry.start.isoformat(),
                "end": entry.end.isoformat(),
                "calendar_event_status": entry.calendar_event_status.value,
            }
            for entry in draft.entries
        ],
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


register_canonicalizer("v1", _canonicalize_v1)
