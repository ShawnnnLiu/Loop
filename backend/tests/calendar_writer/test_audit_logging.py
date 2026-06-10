"""Tests for the hash-check audit log and the typed-exception boundary.

The approval-event spec mandates that every hash check (pass, mismatch,
expired) is logged with the approval id, the approved hash, the recomputed
hash, and the result. The errors module promises that every
``CalendarWriterError`` subclass is translated at the manager boundary into
the ``WriteResult`` matching its ``reason_code``.
"""

from __future__ import annotations

import logging

import pytest

from agentic_calendar.calendar_writer.errors import (
    ApprovalExpiredError,
    ApprovalHashAlgorithmUnsupportedError,
    ApprovalHashMismatchError,
    ApprovalMissingError,
    CalendarWriteFailedError,
    CalendarWriterError,
    ExternalSyncFailedError,
)
from agentic_calendar.contracts.reason_codes import ReasonCode
from tests.calendar_writer.test_manager import (
    _approval_for,
    _draft,
    _make_manager,
)

_AUDIT_LOGGER = "agentic_calendar.calendar_writer.manager"


@pytest.mark.parametrize(
    ("exc_type", "expected_reason"),
    [
        (ApprovalMissingError, ReasonCode.APPROVAL_MISSING),
        (ApprovalExpiredError, ReasonCode.APPROVAL_EXPIRED),
        (ApprovalHashMismatchError, ReasonCode.APPROVAL_HASH_MISMATCH),
        (
            ApprovalHashAlgorithmUnsupportedError,
            ReasonCode.APPROVAL_HASH_ALGORITHM_UNSUPPORTED,
        ),
        (CalendarWriteFailedError, ReasonCode.CALENDAR_WRITE_FAILED),
        (ExternalSyncFailedError, ReasonCode.EXTERNAL_SYNC_FAILED),
    ],
)
def test_every_writer_error_carries_its_matching_reason_code(
    exc_type: type[CalendarWriterError], expected_reason: ReasonCode
) -> None:
    assert exc_type.reason_code is expected_reason


def test_hash_check_pass_emits_audit_log(caplog: pytest.LogCaptureFixture) -> None:
    mgr, _, _, approval_store, _, _ = _make_manager()
    draft = _draft()
    approval = _approval_for(draft)
    approval_store.save(approval)

    with caplog.at_level(logging.INFO, logger=_AUDIT_LOGGER):
        result = mgr.approve_and_write(
            approval_event_id=approval.approval_event_id,
            draft=draft,
            target_calendar_id="primary",
        )

    assert result.status.value == "success"
    pass_records = [
        r for r in caplog.records if "approval hash check: result=pass" in r.getMessage()
    ]
    assert len(pass_records) == 1
    message = pass_records[0].getMessage()
    # Spec-mandated fields: approval id, approved hash, recomputed hash, result.
    assert approval.approval_event_id in message
    assert approval.approved_payload_hash in message
    assert f"recomputed_hash={approval.approved_payload_hash}" in message


def test_hash_check_mismatch_emits_error_level_audit_log(
    caplog: pytest.LogCaptureFixture,
) -> None:
    mgr, _, _, approval_store, _, _ = _make_manager()
    draft = _draft()
    approval = _approval_for(draft, override_hash="sha256:" + "0" * 64)
    approval_store.save(approval)

    with caplog.at_level(logging.INFO, logger=_AUDIT_LOGGER):
        result = mgr.approve_and_write(
            approval_event_id=approval.approval_event_id,
            draft=draft,
            target_calendar_id="primary",
        )

    assert result.reason_code is ReasonCode.APPROVAL_HASH_MISMATCH
    mismatch_records = [
        r
        for r in caplog.records
        if "approval hash check: result=mismatch" in r.getMessage()
    ]
    assert len(mismatch_records) == 1
    assert mismatch_records[0].levelno == logging.ERROR  # P1 incident severity
    message = mismatch_records[0].getMessage()
    assert approval.approval_event_id in message
    assert approval.approved_payload_hash in message  # approved hash
    assert "recomputed_hash=sha256:" in message  # recomputed hash


def test_hash_check_expired_emits_audit_log(
    caplog: pytest.LogCaptureFixture,
) -> None:
    from datetime import timedelta

    from agentic_calendar.common.clock import FrozenClock
    from tests.calendar_writer.test_manager import _NOW

    # Approval is valid at creation but the clock has moved past expiry.
    mgr, _, _, approval_store, _, _ = _make_manager(
        clock=FrozenClock(_NOW + timedelta(hours=48))
    )
    draft = _draft()
    approval = _approval_for(draft, expires_at=_NOW + timedelta(hours=24))
    approval_store.save(approval)

    with caplog.at_level(logging.INFO, logger=_AUDIT_LOGGER):
        result = mgr.approve_and_write(
            approval_event_id=approval.approval_event_id,
            draft=draft,
            target_calendar_id="primary",
        )

    assert result.reason_code is ReasonCode.APPROVAL_EXPIRED
    expired_records = [
        r
        for r in caplog.records
        if "approval hash check: result=expired" in r.getMessage()
    ]
    assert len(expired_records) == 1
    assert approval.approval_event_id in expired_records[0].getMessage()
