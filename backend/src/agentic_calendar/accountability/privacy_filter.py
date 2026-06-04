"""Deterministic sponsor-report privacy filter (Phase 3).

Spec: ``docs/specs/sponsor-report.schema.md`` ("Privacy Denylist"),
``docs/axioms/21-accountability-layer.md`` ("Privacy Constraints").

This filter is the hard boundary between a user's private progress data and a
sponsor. It runs **before** any LLM wording pass and again on the final payload
**before** send (golden scenarios 19, 25). Two separable jobs:

1. ``strip_to_visibility`` — deterministically drop fields a visibility level
   does not permit (e.g. ``task_completion_summary`` below ``task_completion``).
   This is silent field removal, not a violation: a visibility *downgrade* still
   produces a valid report, just with less detail (scenario 20).

2. ``scan`` — reject *denylisted* content (raw calendar titles, essay drafts,
   private notes, psychological labels) with
   :attr:`ReasonCode.SPONSOR_VISIBILITY_VIOLATION`. Denylisted content is a
   trust violation, never silently stripped — the draft is blocked and flagged
   for engineering review (scenario 19).

The **strong** guarantee is structural: the report model
(:class:`SponsorReport`) has a fixed allowlist of fields and ``extra="forbid"``,
so the LLM never sees a disallowed field. The denylist key/marker scan below is
defense-in-depth for payloads assembled from untrusted sources (e.g. an LLM
wording pass that returns extra keys, or a free-text field that embeds private
content). The marker list is a heuristic prior, not a content classifier
(axiom: heuristic priors until calibrated); callers may extend it.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from agentic_calendar.contracts.motivation_profile import SponsorVisibility
from agentic_calendar.contracts.reason_codes import ReasonCode

#: Structured keys that must never appear in a sponsor payload. Presence of any
#: of these is an immediate violation regardless of value (axiom 21 privacy
#: constraints). Matched case-insensitively against payload keys.
DENYLIST_KEYS: frozenset[str] = frozenset(
    {
        "calendar_title",
        "calendar_event_title",
        "raw_calendar_title",
        "calendar_description",
        "calendar_event_description",
        "raw_calendar_description",
        "essay_draft",
        "essay_text",
        "draft_text",
        "private_note",
        "private_notes",
        "notes",
        "reflection",
        "emotional_reflection",
        "health_info",
        "health",
        "relationship_info",
        "psychological_label",
        "diagnosis",
    }
)

#: Case-insensitive substrings that tag disallowed content embedded in a
#: free-text field (milestone names, suggested support action). Heuristic prior.
DEFAULT_DENYLIST_MARKERS: tuple[str, ...] = (
    "calendar title:",
    "essay draft:",
    "private note:",
    "diagnosis:",
    "[essay-draft]",
    "[private]",
    "[health]",
)

#: Report fields whose string values are scanned for denylist markers.
_TEXT_FIELDS: tuple[str, ...] = ("milestone_summary", "suggested_support_action")

#: Visibility level → the set of optional body fields it additionally permits
#: beyond the always-included summary fields. ``task_completion_summary`` is the
#: only level-gated field in the MVP, so ``milestone_progress`` and
#: ``summary_only`` produce structurally identical reports (both carry
#: ``milestone_summary`` and no task detail); only ``task_completion`` unlocks an
#: extra field. A future phase may gate more fields per level here.
_LEVEL_GATED_FIELDS: dict[str, frozenset[str]] = {
    "task_completion_summary": frozenset({SponsorVisibility.TASK_COMPLETION.value}),
}


@dataclass(frozen=True)
class PrivacyVerdict:
    """Outcome of a privacy scan.

    ``ok`` is true when nothing denylisted was found. When false,
    ``reason_code`` is :attr:`ReasonCode.SPONSOR_VISIBILITY_VIOLATION` and
    ``offending_fields`` names the keys/fields that tripped the filter (for the
    engineering-review log, never the offending *values*).
    """

    ok: bool
    reason_code: ReasonCode | None = None
    offending_fields: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def clean(cls) -> PrivacyVerdict:
        return cls(ok=True)

    @classmethod
    def violation(cls, offending_fields: Iterable[str]) -> PrivacyVerdict:
        return cls(
            ok=False,
            reason_code=ReasonCode.SPONSOR_VISIBILITY_VIOLATION,
            offending_fields=tuple(sorted(set(offending_fields))),
        )


class PrivacyFilter:
    """Stateless deterministic privacy enforcement for sponsor payloads."""

    def __init__(self, *, extra_denylist_markers: Iterable[str] = ()) -> None:
        self._markers: tuple[str, ...] = DEFAULT_DENYLIST_MARKERS + tuple(
            m.lower() for m in extra_denylist_markers
        )

    def strip_to_visibility(
        self, payload: Mapping[str, Any], visibility: SponsorVisibility
    ) -> dict[str, Any]:
        """Return ``payload`` with fields not permitted at ``visibility`` removed.

        Silent, deterministic field removal — used to realize a visibility
        downgrade (scenario 20). Does **not** inspect for denylisted content;
        call :meth:`scan` for that.
        """
        out: dict[str, Any] = {}
        for key, value in payload.items():
            allowed_levels = _LEVEL_GATED_FIELDS.get(key)
            if allowed_levels is not None and visibility.value not in allowed_levels:
                continue
            out[key] = value
        return out

    def scan(self, payload: Mapping[str, Any], visibility: SponsorVisibility) -> PrivacyVerdict:
        """Reject any denylisted key, level-violating field, or text marker.

        Unlike :meth:`strip_to_visibility`, a level-gated field that survives to
        this point *is* reported as offending — by the time a payload reaches a
        scan it should already have been stripped, so an over-level field here
        signals a generator bug rather than a benign downgrade.
        """
        offending: list[str] = []

        for key in payload:
            if key.lower() in DENYLIST_KEYS:
                offending.append(key)

        for key, allowed_levels in _LEVEL_GATED_FIELDS.items():
            if (
                key in payload
                and payload[key] is not None
                and visibility.value not in allowed_levels
            ):
                offending.append(key)

        for field_name in _TEXT_FIELDS:
            value = payload.get(field_name)
            if self._text_has_marker(value):
                offending.append(field_name)

        if offending:
            return PrivacyVerdict.violation(offending)
        return PrivacyVerdict.clean()

    def _text_has_marker(self, value: Any) -> bool:
        """True if any denylist marker appears in ``value`` (recursively)."""
        if value is None:
            return False
        if isinstance(value, str):
            lowered = value.lower()
            return any(marker in lowered for marker in self._markers)
        if isinstance(value, Mapping):
            # Scan keys as well as values: an untrusted (e.g. LLM-assembled)
            # payload could embed disallowed content in a key name.
            return any(
                self._text_has_marker(k) or self._text_has_marker(v) for k, v in value.items()
            )
        if isinstance(value, (list, tuple)):
            return any(self._text_has_marker(v) for v in value)
        return False
