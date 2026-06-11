"""Consent gate: the single auditable entry point for consent-scoped reads.

Every pooled-training, pooled-serving, and cohort-retrieval access must pass
:meth:`ConsentGate.check` before touching a user's data (ADR-0007). The gate
is deterministic: it resolves the active :class:`ConsentRecord` for the
purpose's scope, decides allow/deny with a typed reason code, and writes
exactly one :class:`DataAccessAuditEntry` per check — allowed or denied — so
the audit log alone answers "who touched whose data, why, and with what
outcome".

Denial never raises: pooled absence must not block planning (phase plan
acceptance criteria), so callers branch on :attr:`ConsentDecision.allowed`
and fall back deterministically.
"""

from __future__ import annotations

from dataclasses import dataclass

from agentic_calendar.common.clock import Clock
from agentic_calendar.common.ids import IdGenerator
from agentic_calendar.contracts.consent_record import ConsentScope
from agentic_calendar.contracts.data_access_audit import (
    DataAccessAuditEntry,
    DataAccessor,
    DataAccessOutcome,
    DataAccessPurpose,
)
from agentic_calendar.contracts.reason_codes import ReasonCode

from .audit_store import DataAccessAuditStore
from .store import ConsentStore

#: Consent scope each gated purpose consults (data-access-audit spec table).
#: Data-control purposes are absent on purpose: they never pass through the
#: gate (a user always controls their own data).
GATED_PURPOSE_TO_SCOPE: dict[DataAccessPurpose, ConsentScope] = {
    DataAccessPurpose.POOLED_TRAINING: ConsentScope.POOLED_TRAINING,
    DataAccessPurpose.POOLED_SERVING: ConsentScope.POOLED_TRAINING,
    DataAccessPurpose.COHORT_RETRIEVAL: ConsentScope.COHORT_RETRIEVAL,
}


@dataclass(frozen=True)
class ConsentDecision:
    """Outcome of one gate check, with the audit entry already written."""

    allowed: bool
    reason_code: ReasonCode | None
    audit_entry: DataAccessAuditEntry


class ConsentGate:
    """Deterministic allow/deny gate over a consent store, fully audited.

    ``required_consent_version``, when set, pins the consent-language version
    the current terms require: an active grant for any other version is
    treated as missing consent for the current terms (consent-record spec
    ``consent_version`` semantics).
    """

    def __init__(
        self,
        consent_store: ConsentStore,
        audit_store: DataAccessAuditStore,
        *,
        clock: Clock,
        id_generator: IdGenerator,
        required_consent_version: str | None = None,
    ) -> None:
        self._consents = consent_store
        self._audit = audit_store
        self._clock = clock
        self._ids = id_generator
        self._required_version = required_consent_version

    def check(
        self,
        user_id: str,
        purpose: DataAccessPurpose,
        accessor: DataAccessor,
    ) -> ConsentDecision:
        """Decide one consent-scoped access and write its audit entry.

        Raises ``ValueError`` for data-control purposes — those are handled
        by ``data_controls.py`` and never consent-checked.
        """
        scope = GATED_PURPOSE_TO_SCOPE.get(purpose)
        if scope is None:
            raise ValueError(
                f"purpose '{purpose.value}' is a data control, not a consent-gated access"
            )

        reason_code = self._deny_reason(user_id, scope)
        allowed = reason_code is None
        entry = DataAccessAuditEntry(
            audit_entry_id=self._ids.new_id("audit"),
            user_id=user_id,
            purpose=purpose,
            accessor=accessor,
            outcome=DataAccessOutcome.ALLOWED if allowed else DataAccessOutcome.DENIED,
            reason_code=reason_code,
            created_at=self._clock.now(),
        )
        self._audit.append(entry)
        return ConsentDecision(allowed=allowed, reason_code=reason_code, audit_entry=entry)

    def _deny_reason(self, user_id: str, scope: ConsentScope) -> ReasonCode | None:
        """Return the typed denial code, or None when access is allowed."""
        active = self._consents.get_active(user_id, scope)
        if active is not None:
            if (
                self._required_version is not None
                and active.consent_version != self._required_version
            ):
                # Consent for the *current* terms is missing, even though an
                # older-version grant exists (consent-record spec).
                return ReasonCode.CONSENT_MISSING
            return None
        latest = self._consents.latest_for_scope(user_id, scope)
        if latest is None:
            return ReasonCode.CONSENT_MISSING
        return ReasonCode.CONSENT_REVOKED
