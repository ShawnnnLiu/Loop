"""View / export / delete data controls (Phase 6a; ADR-0007).

The phase plan requires that users can view, export, and delete their data.
These operations span stores owned by other regions (telemetry, future
accountability stores), and ``consent/`` is a leaf — so the composition root
passes each store in as a :class:`UserDataSource`: a named, user-scoped view
that can list a user's rows as JSON payloads and delete them. Telemetry has
no ``user_id`` on the event, so its adapter scopes by the user's task ids —
that knowledge lives with the composition root, not here.

Every operation writes one :class:`DataAccessAuditEntry`:

* view → ``allowed`` / null reason code;
* export → ``allowed`` / ``DATA_EXPORTED``;
* delete → ``allowed`` / ``DATA_DELETED``.

Delete removes the user's rows from **every** registered source and from the
consent store. The audit log is deliberately *not* a source: the deletion's
audit trail survives the deletion (data-access-audit spec).
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from agentic_calendar.common.clock import Clock
from agentic_calendar.common.errors import AgenticCalendarError
from agentic_calendar.common.ids import IdGenerator
from agentic_calendar.contracts.data_access_audit import (
    DataAccessAuditEntry,
    DataAccessor,
    DataAccessOutcome,
    DataAccessPurpose,
)
from agentic_calendar.contracts.reason_codes import ReasonCode

from .audit_store import DataAccessAuditStore
from .store import ConsentStore


class DuplicateSourceNameError(AgenticCalendarError):
    """Two registered sources share a name; the bundle would silently merge."""


@runtime_checkable
class UserDataSource(Protocol):
    """One store's user-scoped view, provided by the composition root."""

    @property
    def name(self) -> str:
        """Stable label for this store in export bundles and delete counts."""
        ...

    def list_payloads_for_user(self, user_id: str) -> list[dict[str, Any]]:
        """Return the user's rows as JSON-serializable payloads."""
        ...

    def delete_for_user(self, user_id: str) -> int:
        """Remove the user's rows; return the count removed."""
        ...


#: Reserved bundle keys; a source may not collide with them.
_RESERVED_SOURCE_NAMES = frozenset({"consent_records", "data_access_audit"})

_CONTROL_REASON_CODES: dict[DataAccessPurpose, ReasonCode | None] = {
    DataAccessPurpose.DATA_VIEW: None,
    DataAccessPurpose.DATA_EXPORT: ReasonCode.DATA_EXPORTED,
    DataAccessPurpose.DATA_DELETE: ReasonCode.DATA_DELETED,
}


def _check_source_names(sources: list[UserDataSource]) -> None:
    seen: set[str] = set()
    for source in sources:
        if source.name in seen or source.name in _RESERVED_SOURCE_NAMES:
            raise DuplicateSourceNameError(source.name)
        seen.add(source.name)


def _audit_control(
    user_id: str,
    purpose: DataAccessPurpose,
    accessor: DataAccessor,
    audit_store: DataAccessAuditStore,
    clock: Clock,
    id_generator: IdGenerator,
) -> DataAccessAuditEntry:
    entry = DataAccessAuditEntry(
        audit_entry_id=id_generator.new_id("audit"),
        user_id=user_id,
        purpose=purpose,
        accessor=accessor,
        outcome=DataAccessOutcome.ALLOWED,
        reason_code=_CONTROL_REASON_CODES[purpose],
        created_at=clock.now(),
    )
    audit_store.append(entry)
    return entry


def collect_user_data(
    user_id: str,
    sources: list[UserDataSource],
    *,
    consent_store: ConsentStore,
    audit_store: DataAccessAuditStore,
    clock: Clock,
    id_generator: IdGenerator,
    accessor: DataAccessor,
    purpose: DataAccessPurpose = DataAccessPurpose.DATA_VIEW,
) -> dict[str, Any]:
    """Bundle all-and-only ``user_id``'s data for view or export.

    The bundle always includes the user's consent records and their audit
    entries (they are the user's data too), plus one key per registered
    source. The audit entry for *this* operation is written after the bundle
    is collected, so a view does not list itself.
    """
    if purpose not in (DataAccessPurpose.DATA_VIEW, DataAccessPurpose.DATA_EXPORT):
        raise ValueError(f"collect_user_data does not handle purpose '{purpose.value}'")
    _check_source_names(sources)

    bundle: dict[str, Any] = {
        "user_id": user_id,
        "consent_records": [
            r.model_dump(mode="json") for r in consent_store.list_for_user(user_id)
        ],
        "data_access_audit": [
            e.model_dump(mode="json") for e in audit_store.list_for_user(user_id)
        ],
        "stores": {s.name: s.list_payloads_for_user(user_id) for s in sources},
    }
    _audit_control(user_id, purpose, accessor, audit_store, clock, id_generator)
    return bundle


def delete_user_data(
    user_id: str,
    sources: list[UserDataSource],
    *,
    consent_store: ConsentStore,
    audit_store: DataAccessAuditStore,
    clock: Clock,
    id_generator: IdGenerator,
    accessor: DataAccessor,
) -> dict[str, int]:
    """Delete ``user_id``'s rows from every registered source, audited.

    Returns per-source deletion counts (plus ``consent_records``). The
    ``DATA_DELETED`` audit entry is written after the deletions complete and
    is retained — audit entries are never a deletion target.
    """
    _check_source_names(sources)
    counts: dict[str, int] = {s.name: s.delete_for_user(user_id) for s in sources}
    counts["consent_records"] = consent_store.delete_for_user(user_id)
    _audit_control(
        user_id, DataAccessPurpose.DATA_DELETE, accessor, audit_store, clock, id_generator
    )
    return counts
