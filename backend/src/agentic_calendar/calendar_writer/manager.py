"""Calendar Write Manager — the only writer to an external calendar.

Per axiom 06 line 18, every external calendar mutation flows through this
class. The manager orchestrates the full write flow per axiom 06 lines
97-108, including the mandatory hash recheck per lines 181-189 and the
partial-failure recovery per lines 110-118.

The manager NEVER auto-retries (axiom 06 lines 226-232). The
:meth:`reconcile_after_crash` method is the only re-entry path; it is meant
to be called by the user-triggered manual-retry UX, not by an internal timer.

Determinism: the manager takes :class:`Clock` and :class:`IdGenerator` via
dependency injection; it does not call ``datetime.now()`` or any RNG
directly. Operator CLIs wire ``FrozenClock`` + ``DeterministicIdGenerator``
so output is byte-stable.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from agentic_calendar.approval.store import (
    ApprovalEventNotFoundError,
    ApprovalEventStore,
)
from agentic_calendar.common.clock import Clock
from agentic_calendar.common.ids import IdGenerator
from agentic_calendar.contracts.approval_event import HashAlgorithm
from agentic_calendar.contracts.calendar_event_mapping import (
    CalendarEventMapping,
    CalendarWriteStatus,
)
from agentic_calendar.contracts.draft_schedule import DraftSchedule
from agentic_calendar.contracts.hashing import (
    UnsupportedCanonicalizationVersionError,
    verify_payload_hash,
)
from agentic_calendar.contracts.reason_codes import ReasonCode

from .adapter import ExternalCalendarAdapter
from .lock import (
    CalendarWriteLockBusyError,
    CalendarWriteLockExpiredError,
    CalendarWriteLockManager,
    LockToken,
)
from .metadata import build_event_metadata
from .rollback import RollbackResult, rollback_run
from .store import CalendarEventMappingStore
from .verification import VerificationResult, verify_run


class WriteStatus(StrEnum):
    SUCCESS = "success"
    PARTIAL_FAILURE = "partial_failure"
    ABORTED_PRE_WRITE = "aborted_pre_write"
    LOCK_BUSY = "lock_busy"


@dataclass(frozen=True, slots=True)
class PlannedEvent:
    """A single event that ``preview`` says will be created."""

    task_id: str
    scheduled_start: object
    scheduled_end: object
    metadata: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class PreviewResult:
    """Pure preview of what a draft would write, plus the canonical hash."""

    draft_schedule_id: str
    planned_events: tuple[PlannedEvent, ...]
    draft_payload_hash: str


@dataclass(frozen=True, slots=True)
class WriteResult:
    """Terminal result of ``approve_and_write`` or ``reconcile_after_crash``."""

    run_id: str | None
    status: WriteStatus
    reason_code: ReasonCode | None
    written_mappings: tuple[CalendarEventMapping, ...]
    verification: VerificationResult | None


# Reason codes that map to ABORTED_PRE_WRITE (no external API call was made).
_ABORT_REASONS = frozenset(
    {
        ReasonCode.APPROVAL_MISSING,
        ReasonCode.APPROVAL_EXPIRED,
        ReasonCode.APPROVAL_HASH_MISMATCH,
        ReasonCode.APPROVAL_HASH_ALGORITHM_UNSUPPORTED,
        ReasonCode.CALENDAR_WRITE_DUPLICATE_DETECTED,
    }
)


class CalendarWriteManager:
    """The sole entry point for external calendar writes."""

    def __init__(
        self,
        *,
        adapter: ExternalCalendarAdapter,
        mapping_store: CalendarEventMappingStore,
        approval_store: ApprovalEventStore,
        lock_manager: CalendarWriteLockManager,
        id_generator: IdGenerator,
        clock: Clock,
    ) -> None:
        self._adapter = adapter
        self._mapping_store = mapping_store
        self._approval_store = approval_store
        self._lock_manager = lock_manager
        self._id_generator = id_generator
        self._clock = clock

    # ------------------------------------------------------------------ #
    # preview
    # ------------------------------------------------------------------ #

    def preview(
        self,
        *,
        draft: DraftSchedule,
        target_calendar_id: str,
        canonicalization_version: str = "v1",
    ) -> PreviewResult:
        """Compute what a write would do without touching the adapter.

        Returns the canonical payload hash so the caller can show it to the
        user before they click "approve" — the approval will record the same
        hash and the write-time recheck (per axiom 06 lines 181-189) will
        catch any drift.
        """
        # Hashing uses a synthetic preview run_id so the metadata builder
        # exercises the same path as the real write; it is NOT persisted.
        preview_run_id = self._id_generator.new_id("preview_run")
        planned = tuple(
            PlannedEvent(
                task_id=entry.task_id,
                scheduled_start=entry.start,
                scheduled_end=entry.end,
                metadata=build_event_metadata(
                    run_id=preview_run_id,
                    plan_version=draft.plan_version,
                    task_id=entry.task_id,
                ),
            )
            for entry in draft.entries
        )
        from agentic_calendar.contracts.hashing import canonical_payload_hash

        return PreviewResult(
            draft_schedule_id=draft.draft_schedule_id,
            planned_events=planned,
            draft_payload_hash=canonical_payload_hash(draft, canonicalization_version),
        )

    # ------------------------------------------------------------------ #
    # approve_and_write
    # ------------------------------------------------------------------ #

    def approve_and_write(
        self,
        *,
        approval_event_id: str,
        draft: DraftSchedule,
        target_calendar_id: str,
    ) -> WriteResult:
        """Execute the full approved-write flow.

        Algorithm (axiom 06 lines 97-108 + 181-189):

        1. Load the approval; reject if missing / expired / unsupported algorithm.
        2. Recompute the payload hash against ``draft``. Mismatch → abort with
           ``APPROVAL_HASH_MISMATCH``. No adapter call yet.
        3. Acquire the per-user lock with a fresh ``run_id``.
        4. Duplicate guard: query the adapter for events tagged with this
           ``run_id``. Non-empty → abort with ``CALENDAR_WRITE_DUPLICATE_DETECTED``.
        5. For each entry, build metadata, ``adapter.create_event``,
           ``mapping_store.save`` with ``WRITTEN`` status, ``lock_manager.heartbeat``.
        6. Run ``verify_run``. On success, mark each mapping ``VERIFIED`` and
           emit ``WriteResult(status=SUCCESS)``. On failure, mark unverified
           mappings ``VERIFICATION_FAILED``, emit
           ``WriteResult(status=PARTIAL_FAILURE, reason_code=EXTERNAL_SYNC_FAILED)``.
           **No auto-retry.**
        7. Release the lock in ``finally``.
        """
        # --- Step 1: load + validate approval ----------------------------
        try:
            approval = self._approval_store.get(approval_event_id)
        except ApprovalEventNotFoundError:
            return self._aborted(ReasonCode.APPROVAL_MISSING, run_id=None)

        now = self._clock.now()
        if approval.expires_at <= now:
            return self._aborted(ReasonCode.APPROVAL_EXPIRED, run_id=None)

        if approval.hash_algorithm is not HashAlgorithm.SHA256:
            return self._aborted(
                ReasonCode.APPROVAL_HASH_ALGORITHM_UNSUPPORTED, run_id=None
            )

        # --- Step 2: mandatory hash recheck (axiom 06 lines 181-189) ----
        try:
            hash_ok = verify_payload_hash(
                draft,
                approval.approved_payload_hash,
                approval.hash_canonicalization_version,
            )
        except UnsupportedCanonicalizationVersionError:
            return self._aborted(
                ReasonCode.APPROVAL_HASH_ALGORITHM_UNSUPPORTED, run_id=None
            )
        if not hash_ok:
            return self._aborted(ReasonCode.APPROVAL_HASH_MISMATCH, run_id=None)

        # --- Step 3: acquire lock ---------------------------------------
        run_id = self._id_generator.new_id("run")
        try:
            token = self._lock_manager.acquire(
                user_id=approval.user_id, run_id=run_id
            )
        except CalendarWriteLockBusyError:
            return WriteResult(
                run_id=run_id,
                status=WriteStatus.LOCK_BUSY,
                reason_code=ReasonCode.CALENDAR_WRITE_LOCK_BUSY,
                written_mappings=(),
                verification=None,
            )

        try:
            # --- Step 4: duplicate guard --------------------------------
            duplicates = self._adapter.query_events_by_metadata(
                target_calendar_id=target_calendar_id, run_id=run_id
            )
            if duplicates:
                return self._aborted(
                    ReasonCode.CALENDAR_WRITE_DUPLICATE_DETECTED, run_id=run_id
                )

            # --- Step 5: per-task create + persist ----------------------
            written, partial_create_failure = self._create_events(
                draft=draft,
                run_id=run_id,
                target_calendar_id=target_calendar_id,
                token=token,
            )

            if partial_create_failure:
                # An adapter create raised; the run is doomed. Stop writing,
                # mark verification step as not run, return PARTIAL_FAILURE.
                return WriteResult(
                    run_id=run_id,
                    status=WriteStatus.PARTIAL_FAILURE,
                    reason_code=ReasonCode.CALENDAR_WRITE_FAILED,
                    written_mappings=tuple(written),
                    verification=None,
                )

            # --- Step 6: verify -----------------------------------------
            verification = verify_run(
                run_id=run_id,
                expected_mappings=written,
                adapter=self._adapter,
                target_calendar_id=target_calendar_id,
                clock=self._clock,
            )
            updated = self._apply_verification(written, verification)

            if verification.all_verified:
                return WriteResult(
                    run_id=run_id,
                    status=WriteStatus.SUCCESS,
                    reason_code=None,
                    written_mappings=tuple(updated),
                    verification=verification,
                )

            # No auto-retry per axiom 06 lines 226-232.
            return WriteResult(
                run_id=run_id,
                status=WriteStatus.PARTIAL_FAILURE,
                reason_code=ReasonCode.EXTERNAL_SYNC_FAILED,
                written_mappings=tuple(updated),
                verification=verification,
            )
        finally:
            # --- Step 7: release lock -----------------------------------
            self._lock_manager.release(token)

    # ------------------------------------------------------------------ #
    # verify / rollback / reconcile
    # ------------------------------------------------------------------ #

    def verify(
        self, *, run_id: str, target_calendar_id: str
    ) -> VerificationResult:
        """Re-verify every mapping for ``run_id`` (idempotent, no mutations)."""
        mappings = self._mapping_store.list_for_run(run_id)
        return verify_run(
            run_id=run_id,
            expected_mappings=mappings,
            adapter=self._adapter,
            target_calendar_id=target_calendar_id,
            clock=self._clock,
        )

    def rollback(
        self, *, run_id: str, target_calendar_id: str
    ) -> RollbackResult:
        """Delete every external event for ``run_id``, marking mappings accordingly."""
        mappings = self._mapping_store.list_for_run(run_id)
        # Transition each mapping into ROLLBACK_PENDING before invoking the
        # adapter so a crash mid-rollback leaves a queryable in-progress state.
        now = self._clock.now()
        for mapping in mappings:
            if mapping.calendar_write_status in {
                CalendarWriteStatus.ROLLED_BACK,
                CalendarWriteStatus.ROLLBACK_FAILED,
                CalendarWriteStatus.VERIFIED,
            }:
                # Terminal already; only `verified` is allowed to transition
                # into rollback_pending and we permit it via the legal-table
                # if we ever extend; for Phase 2 we honor the table strictly.
                continue
            if mapping.calendar_write_status is CalendarWriteStatus.WRITTEN or (
                mapping.calendar_write_status
                is CalendarWriteStatus.VERIFICATION_FAILED
            ):
                self._mapping_store.update_status(
                    run_id,
                    mapping.task_id,
                    new_status=CalendarWriteStatus.ROLLBACK_PENDING,
                    now=now,
                )

        # Refresh after status changes; rollback_run only inspects
        # calendar_event_id and run_id, but we want the manager's view current.
        mappings = self._mapping_store.list_for_run(run_id)
        result = rollback_run(
            run_id=run_id,
            mappings=mappings,
            adapter=self._adapter,
            target_calendar_id=target_calendar_id,
        )

        # Translate adapter outcomes into mapping status transitions.
        now = self._clock.now()
        failed_ids = set(result.failed_event_ids)
        for mapping in mappings:
            if mapping.calendar_event_id is None:
                continue
            if (
                mapping.calendar_write_status
                is not CalendarWriteStatus.ROLLBACK_PENDING
            ):
                continue
            new_status = (
                CalendarWriteStatus.ROLLBACK_FAILED
                if mapping.calendar_event_id in failed_ids
                else CalendarWriteStatus.ROLLED_BACK
            )
            self._mapping_store.update_status(
                run_id,
                mapping.task_id,
                new_status=new_status,
                now=now,
            )
        return result

    def reconcile_after_crash(
        self, *, run_id: str, target_calendar_id: str, user_id: str
    ) -> WriteResult:
        """Manual-retry path: write only confirmed-missing tasks, then verify.

        Called by the operator/UI after a partial-failure run. Acquires the
        lock, queries the adapter for already-written events tagged with
        ``run_id``, and creates only events that are confirmed missing. Never
        creates duplicates; never auto-runs.
        """
        try:
            token = self._lock_manager.acquire(user_id=user_id, run_id=run_id)
        except CalendarWriteLockBusyError:
            return WriteResult(
                run_id=run_id,
                status=WriteStatus.LOCK_BUSY,
                reason_code=ReasonCode.CALENDAR_WRITE_LOCK_BUSY,
                written_mappings=(),
                verification=None,
            )
        try:
            existing = self._adapter.query_events_by_metadata(
                target_calendar_id=target_calendar_id, run_id=run_id
            )
            existing_task_ids = {
                rec.metadata.get("task_id") for rec in existing if rec.metadata
            }
            mappings = self._mapping_store.list_for_run(run_id)
            now = self._clock.now()

            for mapping in mappings:
                if mapping.task_id in existing_task_ids:
                    continue
                if mapping.calendar_write_status in {
                    CalendarWriteStatus.VERIFIED,
                    CalendarWriteStatus.ROLLED_BACK,
                    CalendarWriteStatus.ROLLBACK_FAILED,
                }:
                    continue
                metadata = build_event_metadata(
                    run_id=run_id,
                    plan_version=mapping.plan_version,
                    task_id=mapping.task_id,
                )
                try:
                    handle = self._adapter.create_event(
                        target_calendar_id=target_calendar_id,
                        scheduled_start=mapping.scheduled_start,
                        scheduled_end=mapping.scheduled_end,
                        metadata=metadata,
                    )
                except Exception:
                    return WriteResult(
                        run_id=run_id,
                        status=WriteStatus.PARTIAL_FAILURE,
                        reason_code=ReasonCode.CALENDAR_WRITE_FAILED,
                        written_mappings=tuple(
                            self._mapping_store.list_for_run(run_id)
                        ),
                        verification=None,
                    )
                # `verification_failed -> written` is permitted only on this
                # manual-retry path (axiom 06 lines 226-232).
                self._mapping_store.update_status(
                    run_id,
                    mapping.task_id,
                    new_status=CalendarWriteStatus.WRITTEN,
                    now=now,
                    calendar_event_id=handle.calendar_event_id,
                )
                try:
                    token = self._lock_manager.heartbeat(token)
                except CalendarWriteLockExpiredError:
                    return WriteResult(
                        run_id=run_id,
                        status=WriteStatus.PARTIAL_FAILURE,
                        reason_code=ReasonCode.CALENDAR_WRITE_LOCK_EXPIRED,
                        written_mappings=tuple(
                            self._mapping_store.list_for_run(run_id)
                        ),
                        verification=None,
                    )

            final_mappings = self._mapping_store.list_for_run(run_id)
            verification = verify_run(
                run_id=run_id,
                expected_mappings=final_mappings,
                adapter=self._adapter,
                target_calendar_id=target_calendar_id,
                clock=self._clock,
            )
            updated = self._apply_verification(final_mappings, verification)
            if verification.all_verified:
                return WriteResult(
                    run_id=run_id,
                    status=WriteStatus.SUCCESS,
                    reason_code=None,
                    written_mappings=tuple(updated),
                    verification=verification,
                )
            return WriteResult(
                run_id=run_id,
                status=WriteStatus.PARTIAL_FAILURE,
                reason_code=ReasonCode.EXTERNAL_SYNC_FAILED,
                written_mappings=tuple(updated),
                verification=verification,
            )
        finally:
            self._lock_manager.release(token)

    # ------------------------------------------------------------------ #
    # internal helpers
    # ------------------------------------------------------------------ #

    def _create_events(
        self,
        *,
        draft: DraftSchedule,
        run_id: str,
        target_calendar_id: str,
        token: LockToken,
    ) -> tuple[list[CalendarEventMapping], bool]:
        """Per-task create + persist loop. Returns (written, had_create_failure)."""
        written: list[CalendarEventMapping] = []
        had_failure = False

        for entry in draft.entries:
            metadata = build_event_metadata(
                run_id=run_id,
                plan_version=draft.plan_version,
                task_id=entry.task_id,
            )
            try:
                handle = self._adapter.create_event(
                    target_calendar_id=target_calendar_id,
                    scheduled_start=entry.start,
                    scheduled_end=entry.end,
                    metadata=metadata,
                )
            except Exception:
                had_failure = True
                break

            mapping = CalendarEventMapping(
                task_id=entry.task_id,
                plan_version=draft.plan_version,
                run_id=run_id,
                calendar_event_id=handle.calendar_event_id,
                scheduled_start=entry.start,
                scheduled_end=entry.end,
                calendar_write_status=CalendarWriteStatus.WRITTEN,
                user_modified_bool=False,
                last_verified_at=None,
            )
            self._mapping_store.save(mapping)
            written.append(mapping)

            try:
                token = self._lock_manager.heartbeat(token)
            except CalendarWriteLockExpiredError:
                had_failure = True
                break

        return written, had_failure

    def _apply_verification(
        self,
        written: list[CalendarEventMapping] | tuple[CalendarEventMapping, ...],
        verification: VerificationResult,
    ) -> list[CalendarEventMapping]:
        """Translate verification outcomes into mapping store transitions.

        Mappings already at the target terminal status are passed through
        unchanged so re-verification (e.g. after ``reconcile_after_crash``)
        does not attempt a VERIFIED -> VERIFIED transition (which the store
        rejects as illegal — VERIFIED is terminal).
        """
        verified = set(verification.verified_task_ids)
        failed = set(verification.failed_task_ids)
        now = self._clock.now()
        updated: list[CalendarEventMapping] = []
        for mapping in written:
            if mapping.task_id in verified:
                if mapping.calendar_write_status is CalendarWriteStatus.VERIFIED:
                    new = mapping
                else:
                    new = self._mapping_store.update_status(
                        mapping.run_id,
                        mapping.task_id,
                        new_status=CalendarWriteStatus.VERIFIED,
                        now=now,
                        calendar_event_id=mapping.calendar_event_id,
                    )
            elif mapping.task_id in failed:
                if (
                    mapping.calendar_write_status
                    is CalendarWriteStatus.VERIFICATION_FAILED
                ):
                    new = mapping
                else:
                    new = self._mapping_store.update_status(
                        mapping.run_id,
                        mapping.task_id,
                        new_status=CalendarWriteStatus.VERIFICATION_FAILED,
                        now=now,
                    )
            else:
                new = mapping
            updated.append(new)
        return updated

    def _aborted(
        self, reason_code: ReasonCode, *, run_id: str | None
    ) -> WriteResult:
        status = (
            WriteStatus.ABORTED_PRE_WRITE
            if reason_code in _ABORT_REASONS
            else WriteStatus.PARTIAL_FAILURE
        )
        return WriteResult(
            run_id=run_id,
            status=status,
            reason_code=reason_code,
            written_mappings=(),
            verification=None,
        )
