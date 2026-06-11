"""Tests for the view/export/delete data controls (Phase 6a; ADR-0007).

These tests compose the consent region with the *real* telemetry event store
(tests may cross regions; src may not — Phase 7 precedent). Telemetry events
carry no ``user_id``, so the composition root scopes them by the user's task
ids; the ``_TaskScopedTelemetrySource`` adapter here is the wiring example.
"""

from __future__ import annotations

from typing import Any

import pytest

from agentic_calendar.common.clock import FrozenClock
from agentic_calendar.common.ids import DeterministicIdGenerator
from agentic_calendar.consent.audit_store import InMemoryDataAccessAuditStore
from agentic_calendar.consent.data_controls import (
    DuplicateSourceNameError,
    UserDataSource,
    collect_user_data,
    delete_user_data,
)
from agentic_calendar.consent.store import InMemoryConsentStore
from agentic_calendar.contracts.consent_record import ConsentScope
from agentic_calendar.contracts.data_access_audit import (
    DataAccessor,
    DataAccessOutcome,
    DataAccessPurpose,
)
from agentic_calendar.contracts.reason_codes import ReasonCode
from agentic_calendar.contracts.telemetry import TelemetryEvent
from agentic_calendar.telemetry.event_store import InMemoryTelemetryEventStore

from ._builders import T0, build_consent_record


class _TaskScopedTelemetrySource:
    """User-scoped view over the real telemetry store, keyed by task ids."""

    def __init__(
        self, store: InMemoryTelemetryEventStore, task_ids_by_user: dict[str, set[str]]
    ) -> None:
        self._store = store
        self._task_ids_by_user = task_ids_by_user

    @property
    def name(self) -> str:
        return "telemetry"

    def list_payloads_for_user(self, user_id: str) -> list[dict[str, Any]]:
        task_ids = self._task_ids_by_user.get(user_id, set())
        return [
            e.model_dump(mode="json") for e in self._store.all() if e.task_id in task_ids
        ]

    def delete_for_user(self, user_id: str) -> int:
        return self._store.delete_for_tasks(self._task_ids_by_user.get(user_id, set()))


def _telemetry_event(event_id: str, task_id: str) -> TelemetryEvent:
    return TelemetryEvent.model_validate(
        {
            "telemetry_event_id": event_id,
            "task_id": task_id,
            "scheduled_duration_min": 60,
            "actual_duration_min": 75,
            "completed": True,
            "completion_timestamp": "2026-06-09T18:00:00-07:00",
            "user_reschedule_count": 0,
            "data_quality": "complete",
        }
    )


def _fixture() -> tuple[
    _TaskScopedTelemetrySource,
    InMemoryTelemetryEventStore,
    InMemoryConsentStore,
    InMemoryDataAccessAuditStore,
    dict[str, Any],
]:
    telemetry = InMemoryTelemetryEventStore()
    telemetry.append(_telemetry_event("tel_001", "task_a1"))
    telemetry.append(_telemetry_event("tel_002", "task_a2"))
    telemetry.append(_telemetry_event("tel_003", "task_b1"))  # other user's
    source = _TaskScopedTelemetrySource(
        telemetry,
        {"user_123": {"task_a1", "task_a2"}, "user_456": {"task_b1"}},
    )
    consents = InMemoryConsentStore(clock=FrozenClock(T0))
    consents.grant(build_consent_record())
    consents.grant(
        build_consent_record(consent_record_id="consent_002", user_id="user_456")
    )
    audit = InMemoryDataAccessAuditStore()
    kwargs: dict[str, Any] = {
        "consent_store": consents,
        "audit_store": audit,
        "clock": FrozenClock(T0),
        "id_generator": DeterministicIdGenerator(),
        "accessor": DataAccessor.OPERATOR_CLI,
    }
    return source, telemetry, consents, audit, kwargs


def test_source_satisfies_protocol() -> None:
    source, *_ = _fixture()
    assert isinstance(source, UserDataSource)


def test_export_contains_all_and_only_the_users_data() -> None:
    source, _, _, _, kwargs = _fixture()
    bundle = collect_user_data(
        "user_123", [source], purpose=DataAccessPurpose.DATA_EXPORT, **kwargs
    )
    assert bundle["user_id"] == "user_123"
    exported_ids = {row["telemetry_event_id"] for row in bundle["stores"]["telemetry"]}
    assert exported_ids == {"tel_001", "tel_002"}  # tel_003 belongs to user_456
    consent_ids = {r["consent_record_id"] for r in bundle["consent_records"]}
    assert consent_ids == {"consent_001"}  # consent_002 belongs to user_456


def test_export_writes_data_exported_audit_entry() -> None:
    source, _, _, audit, kwargs = _fixture()
    bundle = collect_user_data(
        "user_123", [source], purpose=DataAccessPurpose.DATA_EXPORT, **kwargs
    )
    entries = audit.list_for_user("user_123")
    assert len(entries) == 1
    assert entries[0].purpose is DataAccessPurpose.DATA_EXPORT
    assert entries[0].outcome is DataAccessOutcome.ALLOWED
    assert entries[0].reason_code is ReasonCode.DATA_EXPORTED
    # The bundle was collected before the entry was written: a view/export
    # does not list itself.
    assert bundle["data_access_audit"] == []


def test_view_writes_audit_entry_with_null_reason() -> None:
    source, _, _, audit, kwargs = _fixture()
    collect_user_data("user_123", [source], **kwargs)
    entries = audit.list_for_user("user_123")
    assert len(entries) == 1
    assert entries[0].purpose is DataAccessPurpose.DATA_VIEW
    assert entries[0].reason_code is None


def test_collect_rejects_delete_purpose() -> None:
    source, _, _, _, kwargs = _fixture()
    with pytest.raises(ValueError, match="does not handle purpose"):
        collect_user_data(
            "user_123", [source], purpose=DataAccessPurpose.DATA_DELETE, **kwargs
        )


def test_delete_removes_from_every_store_and_is_audited() -> None:
    source, telemetry, consents, audit, kwargs = _fixture()
    counts = delete_user_data("user_123", [source], **kwargs)
    assert counts == {"telemetry": 2, "consent_records": 1}
    # Gone from the real telemetry store; the other user's event remains.
    assert [e.telemetry_event_id for e in telemetry.all()] == ["tel_003"]
    assert consents.list_for_user("user_123") == []
    assert len(consents.list_for_user("user_456")) == 1
    entries = audit.list_for_user("user_123")
    assert len(entries) == 1
    assert entries[0].purpose is DataAccessPurpose.DATA_DELETE
    assert entries[0].reason_code is ReasonCode.DATA_DELETED


def test_deletion_audit_trail_survives_the_deletion() -> None:
    source, _, _, audit, kwargs = _fixture()
    collect_user_data("user_123", [source], **kwargs)  # prior audited view
    delete_user_data("user_123", [source], **kwargs)
    entries = audit.list_for_user("user_123")
    # Both the earlier view and the deletion itself remain in the log.
    assert [e.purpose for e in entries] == [
        DataAccessPurpose.DATA_VIEW,
        DataAccessPurpose.DATA_DELETE,
    ]


def test_second_delete_reports_honest_zero_counts() -> None:
    source, _, _, audit, kwargs = _fixture()
    delete_user_data("user_123", [source], **kwargs)
    counts = delete_user_data("user_123", [source], **kwargs)
    assert counts == {"telemetry": 0, "consent_records": 0}
    # Still audited: two DATA_DELETE entries.
    assert len(audit.list_for_user("user_123")) == 2


def test_duplicate_source_names_rejected() -> None:
    source, _, _, _, kwargs = _fixture()
    other, *_ = _fixture()
    with pytest.raises(DuplicateSourceNameError):
        collect_user_data("user_123", [source, other], **kwargs)


def test_reserved_source_name_rejected() -> None:
    source, telemetry, _, _, kwargs = _fixture()

    class _BadName(_TaskScopedTelemetrySource):
        @property
        def name(self) -> str:
            return "consent_records"

    bad = _BadName(telemetry, {})
    with pytest.raises(DuplicateSourceNameError):
        delete_user_data("user_123", [source, bad], **kwargs)


def test_revoked_user_can_still_export_and_delete() -> None:
    """Data controls never consent-deny: revocation does not strand the data."""
    source, _, consents, audit, kwargs = _fixture()
    consents.revoke("consent_001")
    bundle = collect_user_data(
        "user_123", [source], purpose=DataAccessPurpose.DATA_EXPORT, **kwargs
    )
    assert {r["status"] for r in bundle["consent_records"]} == {"revoked"}
    counts = delete_user_data("user_123", [source], **kwargs)
    assert counts["telemetry"] == 2
    assert all(
        e.outcome is DataAccessOutcome.ALLOWED for e in audit.list_for_user("user_123")
    )


def test_consent_scope_separation_in_bundle() -> None:
    """A user's records for both scopes export together."""
    source, _, consents, _, kwargs = _fixture()
    consents.grant(
        build_consent_record(
            consent_record_id="consent_003", scope=ConsentScope.COHORT_RETRIEVAL
        )
    )
    bundle = collect_user_data("user_123", [source], **kwargs)
    assert {r["scope"] for r in bundle["consent_records"]} == {
        "pooled_training",
        "cohort_retrieval",
    }
