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

from collections.abc import Collection, Mapping
from dataclasses import dataclass
from enum import StrEnum

from agentic_calendar.approval.store import (
    ApprovalEventNotFoundError,
    ApprovalEventStore,
)
from agentic_calendar.common.clock import Clock
from agentic_calendar.common.ids import IdGenerator
from agentic_calendar.common.logging import correlated, get_logger
from agentic_calendar.contracts.approval_event import ApprovalEvent, HashAlgorithm
from agentic_calendar.contracts.calendar_event_mapping import (
    CalendarEventMapping,
    CalendarWriteStatus,
)
from agentic_calendar.contracts.draft_schedule import DraftSchedule
from agentic_calendar.contracts.hashing import (
    UnsupportedCanonicalizationVersionError,
    canonical_payload_hash,
)
from agentic_calendar.contracts.reason_codes import ReasonCode

from .adapter import ExternalCalendarAdapter, ExternalEventRecord
from .errors import (
    ApprovalExpiredError,
    ApprovalHashAlgorithmUnsupportedError,
    ApprovalHashMismatchError,
    ApprovalMissingError,
    CalendarWriteFailedError,
    CalendarWriterError,
    ExternalSyncFailedError,
)
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

_log = get_logger(__name__)


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
    error: str | None = None
    """Human-readable failure detail for operator diagnosability.

    ``str(exc)`` of the typed exception the boundary translated (e.g. the
    Google adapter's enriched provider detail), so the operator sees more
    than the bare ``reason_code``. Adapters guarantee these messages are
    typed error prose only — never raw calendar content or secrets.
    ``None`` on success."""


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
        # --- Steps 1+2: load + validate approval, hash recheck ----------
        try:
            approval = self._validate_approval(
                approval_event_id=approval_event_id, draft=draft
            )
        except CalendarWriterError as exc:
            return self._translate_error(exc, run_id=None)

        # --- Step 3: acquire lock ---------------------------------------
        run_id = self._id_generator.new_id("run")
        try:
            token = self._lock_manager.acquire(
                user_id=approval.user_id, run_id=run_id
            )
        except CalendarWriteLockBusyError as exc:
            return WriteResult(
                run_id=run_id,
                status=WriteStatus.LOCK_BUSY,
                reason_code=ReasonCode.CALENDAR_WRITE_LOCK_BUSY,
                written_mappings=(),
                verification=None,
                error=str(exc),
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
            written = self._create_events(
                draft=draft,
                run_id=run_id,
                target_calendar_id=target_calendar_id,
                token=token,
            )

            # --- Step 6: verify -----------------------------------------
            return self._finalize_run(
                run_id=run_id,
                expected_mappings=written,
                target_calendar_id=target_calendar_id,
            )
        except CalendarWriterError as exc:
            return self._translate_error(exc, run_id=run_id)
        finally:
            # --- Step 7: release lock -----------------------------------
            self._lock_manager.release(token)

    # ------------------------------------------------------------------ #
    # approve_and_remove (delete-only write for a drop)
    # ------------------------------------------------------------------ #

    def approve_and_remove(
        self,
        *,
        approval_event_id: str,
        draft: DraftSchedule,
        removed_task_ids: Collection[str],
        target_calendar_id: str,
    ) -> WriteResult:
        """Delete-only write for a drop: remove the dropped tasks' events.

        Survivor events are left exactly where they are (no create, no update);
        only the ``removed_task_ids`` events are deleted. The approval + hash
        recheck (axiom 06 lines 181-189) is mandatory and validates the
        survivors-only ``draft`` the user approved — deleting the dropped events
        is the deterministic effect of activating that draft. reconcile/status
        read mappings by ``task_id``, so transitioning the dropped tasks' latest
        mappings to ``ROLLED_BACK`` drops them from those views; survivor
        mappings (under their original run) are untouched.

        Reuses the rollback delete + status-transition ceremony (axiom 06 lines
        132-137), scoped to the dropped tasks and gated behind the approval.
        """
        try:
            approval = self._validate_approval(
                approval_event_id=approval_event_id, draft=draft
            )
        except CalendarWriterError as exc:
            return self._translate_error(exc, run_id=None)

        # Latest written mapping per dropped task — that is the live event.
        targets: list[CalendarEventMapping] = []
        for task_id in sorted(set(removed_task_ids)):
            history = self._mapping_store.list_for_task(task_id)
            if not history:
                continue
            latest = history[-1]
            if latest.calendar_event_id is not None and latest.calendar_write_status in {
                CalendarWriteStatus.WRITTEN,
                CalendarWriteStatus.VERIFIED,
                CalendarWriteStatus.VERIFICATION_FAILED,
            }:
                targets.append(latest)

        op_id = self._id_generator.new_id("run")
        if not targets:
            # Nothing on the calendar to remove (idempotent) — the survivor draft
            # is already the live state.
            return WriteResult(
                run_id=op_id,
                status=WriteStatus.SUCCESS,
                reason_code=None,
                written_mappings=(),
                verification=None,
            )

        try:
            token = self._lock_manager.acquire(
                user_id=approval.user_id, run_id=op_id
            )
        except CalendarWriteLockBusyError as exc:
            return WriteResult(
                run_id=op_id,
                status=WriteStatus.LOCK_BUSY,
                reason_code=ReasonCode.CALENDAR_WRITE_LOCK_BUSY,
                written_mappings=(),
                verification=None,
                error=str(exc),
            )
        try:
            now = self._clock.now()
            for mapping in targets:
                self._mapping_store.update_status(
                    mapping.run_id,
                    mapping.task_id,
                    new_status=CalendarWriteStatus.ROLLBACK_PENDING,
                    now=now,
                )
            refreshed = [
                self._mapping_store.get(m.run_id, m.task_id) for m in targets
            ]
            failed: set[str] = set()
            for mapping in refreshed:
                if mapping.calendar_event_id is None:
                    continue
                try:
                    self._adapter.delete_event(
                        target_calendar_id=target_calendar_id,
                        calendar_event_id=mapping.calendar_event_id,
                    )
                except Exception:
                    correlated(_log, run_id=op_id, task_id=mapping.task_id).exception(
                        "adapter.delete_event raised during drop removal "
                        "(reason_code will be CALENDAR_ROLLBACK_FAILED)"
                    )
                    failed.add(mapping.task_id)
            now = self._clock.now()
            updated: list[CalendarEventMapping] = []
            for mapping in refreshed:
                status = (
                    CalendarWriteStatus.ROLLBACK_FAILED
                    if mapping.task_id in failed
                    else CalendarWriteStatus.ROLLED_BACK
                )
                updated.append(
                    self._mapping_store.update_status(
                        mapping.run_id, mapping.task_id, new_status=status, now=now
                    )
                )
            if failed:
                return WriteResult(
                    run_id=op_id,
                    status=WriteStatus.PARTIAL_FAILURE,
                    reason_code=ReasonCode.CALENDAR_ROLLBACK_FAILED,
                    written_mappings=tuple(updated),
                    verification=None,
                    error=f"could not remove dropped events for tasks {sorted(failed)}",
                )
            return WriteResult(
                run_id=op_id,
                status=WriteStatus.SUCCESS,
                reason_code=None,
                written_mappings=tuple(updated),
                verification=None,
            )
        finally:
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

    def read_event(
        self, *, target_calendar_id: str, calendar_event_id: str
    ) -> ExternalEventRecord | None:
        """Read one of the app's own events back from the external calendar
        (``None`` if it no longer exists). A read-only passthrough so inbound
        reconciliation can diff the live calendar against the recorded mappings
        without reaching past the manager — axiom 06's "the Write Manager is the
        only code that touches the calendar". It performs no write."""
        return self._adapter.read_event(
            target_calendar_id=target_calendar_id,
            calendar_event_id=calendar_event_id,
        )

    def rollback(
        self, *, run_id: str, target_calendar_id: str
    ) -> RollbackResult:
        """Delete every external event for ``run_id``, marking mappings accordingly."""
        mappings = self._mapping_store.list_for_run(run_id)
        # Transition each mapping into ROLLBACK_PENDING before invoking the
        # adapter so a crash mid-rollback leaves a queryable in-progress state.
        # VERIFIED is included per axiom 06 lines 132-137: every successful
        # write must be rollback-able.
        now = self._clock.now()
        _ROLLBACKABLE = {
            CalendarWriteStatus.WRITTEN,
            CalendarWriteStatus.VERIFIED,
            CalendarWriteStatus.VERIFICATION_FAILED,
        }
        for mapping in mappings:
            if mapping.calendar_write_status in _ROLLBACKABLE:
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
        self,
        *,
        approval_event_id: str,
        draft: DraftSchedule,
        run_id: str,
        target_calendar_id: str,
    ) -> WriteResult:
        """Manual-retry path: write only confirmed-missing tasks, then verify.

        Called by the operator/UI after a partial-failure run. Per axiom 06
        lines 181-189 the hash recheck is mandatory on every write path, so
        the caller must re-supply the ``approval_event_id`` and the (re-fetched)
        ``draft``; we re-validate the approval and recompute the payload hash
        before touching the adapter. ``user_id`` is taken from the approval to
        eliminate any chance of caller-side mismatch.

        Acquires the lock, queries the adapter for already-written events
        tagged with ``run_id``, and creates only events that are confirmed
        missing. Never creates duplicates; never auto-runs.
        """
        # --- Approval + hash recheck (axiom 06 lines 181-189) ----------
        try:
            approval = self._validate_approval(
                approval_event_id=approval_event_id, draft=draft
            )
        except CalendarWriterError as exc:
            return self._translate_error(exc, run_id=run_id)

        try:
            token = self._lock_manager.acquire(
                user_id=approval.user_id, run_id=run_id
            )
        except CalendarWriteLockBusyError as exc:
            return WriteResult(
                run_id=run_id,
                status=WriteStatus.LOCK_BUSY,
                reason_code=ReasonCode.CALENDAR_WRITE_LOCK_BUSY,
                written_mappings=(),
                verification=None,
                error=str(exc),
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
                except Exception as create_exc:
                    correlated(
                        _log,
                        run_id=run_id,
                        plan_version=mapping.plan_version,
                        task_id=mapping.task_id,
                    ).exception(
                        "adapter.create_event raised during reconcile_after_crash "
                        "(reason_code will be CALENDAR_WRITE_FAILED)"
                    )
                    raise CalendarWriteFailedError(
                        "adapter.create_event raised during reconcile_after_crash",
                        written=tuple(self._mapping_store.list_for_run(run_id)),
                    ) from create_exc
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
                except CalendarWriteLockExpiredError as heartbeat_exc:
                    return WriteResult(
                        run_id=run_id,
                        status=WriteStatus.PARTIAL_FAILURE,
                        reason_code=ReasonCode.CALENDAR_WRITE_LOCK_EXPIRED,
                        written_mappings=tuple(
                            self._mapping_store.list_for_run(run_id)
                        ),
                        verification=None,
                        error=str(heartbeat_exc),
                    )

            return self._finalize_run(
                run_id=run_id,
                expected_mappings=self._mapping_store.list_for_run(run_id),
                target_calendar_id=target_calendar_id,
            )
        except CalendarWriterError as exc:
            return self._translate_error(exc, run_id=run_id)
        finally:
            self._lock_manager.release(token)

    # ------------------------------------------------------------------ #
    # internal helpers
    # ------------------------------------------------------------------ #

    def _validate_approval(
        self,
        *,
        approval_event_id: str,
        draft: DraftSchedule,
    ) -> ApprovalEvent:
        """Steps 1+2 of axiom 06 lines 181-189: load approval, check expiry/
        algorithm, recompute payload hash. Used by both ``approve_and_write``
        and ``reconcile_after_crash`` — the hash recheck is mandatory on every
        write path, not just the first attempt.

        Raises the matching :class:`CalendarWriterError` subclass on any
        failure; the public boundary translates it into a ``WriteResult``.

        Every hash-check outcome (pass, mismatch, expired, unsupported
        algorithm/version) emits a structured audit log carrying the approval
        id, the approved hash, the recomputed hash, and the result
        (approval-event spec, audit-logging section).
        """
        try:
            approval = self._approval_store.get(approval_event_id)
        except ApprovalEventNotFoundError as exc:
            correlated(_log, approval_event_id=approval_event_id).warning(
                "approval hash check: result=approval_missing"
            )
            raise ApprovalMissingError(
                f"no approval event found for id {approval_event_id!r}"
            ) from exc

        audit = correlated(
            _log,
            approval_event_id=approval_event_id,
            approved_hash=approval.approved_payload_hash,
        )

        now = self._clock.now()
        if approval.expires_at <= now:
            audit.warning(
                "approval hash check: result=expired "
                f"expires_at={approval.expires_at.isoformat()} now={now.isoformat()}"
            )
            raise ApprovalExpiredError(
                f"approval {approval_event_id!r} expired at "
                f"{approval.expires_at.isoformat()}"
            )

        if approval.hash_algorithm is not HashAlgorithm.SHA256:
            audit.warning(
                "approval hash check: result=algorithm_unsupported "
                f"hash_algorithm={approval.hash_algorithm}"
            )
            raise ApprovalHashAlgorithmUnsupportedError(
                f"unsupported hash algorithm {approval.hash_algorithm!r}"
            )

        try:
            recomputed = canonical_payload_hash(
                draft, approval.hash_canonicalization_version
            )
        except UnsupportedCanonicalizationVersionError as exc:
            audit.warning(
                "approval hash check: result=canonicalization_unsupported "
                f"version={approval.hash_canonicalization_version!r}"
            )
            raise ApprovalHashAlgorithmUnsupportedError(
                "unsupported hash canonicalization version "
                f"{approval.hash_canonicalization_version!r}"
            ) from exc

        if recomputed != approval.approved_payload_hash:
            audit.error(
                "approval hash check: result=mismatch "
                f"recomputed_hash={recomputed} — P1 incident (axiom 06 line 208)"
            )
            raise ApprovalHashMismatchError(
                f"recomputed payload hash {recomputed} does not match approved "
                f"hash for approval {approval_event_id!r}"
            )

        audit.info(f"approval hash check: result=pass recomputed_hash={recomputed}")
        return approval

    def _create_events(
        self,
        *,
        draft: DraftSchedule,
        run_id: str,
        target_calendar_id: str,
        token: LockToken,
    ) -> list[CalendarEventMapping]:
        """Per-task create + persist loop.

        Raises :class:`CalendarWriteFailedError` carrying the mappings written
        so far when an adapter create raises or the lock heartbeat expires
        mid-loop; the run is doomed and the boundary translates to
        ``PARTIAL_FAILURE`` / ``CALENDAR_WRITE_FAILED``.
        """
        written: list[CalendarEventMapping] = []

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
            except Exception as create_exc:
                correlated(
                    _log,
                    run_id=run_id,
                    plan_version=draft.plan_version,
                    task_id=entry.task_id,
                ).exception(
                    "adapter.create_event raised; aborting per-task loop "
                    "(reason_code will be CALENDAR_WRITE_FAILED)"
                )
                raise CalendarWriteFailedError(
                    "adapter.create_event raised mid-write",
                    written=tuple(written),
                ) from create_exc

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
            except CalendarWriteLockExpiredError as lock_exc:
                raise CalendarWriteFailedError(
                    "lock heartbeat expired mid-write",
                    written=tuple(written),
                ) from lock_exc

        return written

    def _apply_verification(
        self,
        written: list[CalendarEventMapping] | tuple[CalendarEventMapping, ...],
        verification: VerificationResult,
    ) -> list[CalendarEventMapping]:
        """Translate verification outcomes into mapping store transitions.

        Mappings already at the target verification status are passed through
        unchanged so re-verification (e.g. after ``reconcile_after_crash``)
        does not attempt a no-op self-transition like VERIFIED -> VERIFIED,
        which the store rejects as illegal.
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

    def _finalize_run(
        self,
        *,
        run_id: str,
        expected_mappings: list[CalendarEventMapping]
        | tuple[CalendarEventMapping, ...],
        target_calendar_id: str,
    ) -> WriteResult:
        """Step 6: verify the run and translate the outcome.

        Returns the ``SUCCESS`` result when everything verifies. Raises
        :class:`ExternalSyncFailedError` (carrying the updated mappings and
        the verification record) otherwise — no auto-retry per axiom 06
        lines 226-232; the boundary translates it to ``PARTIAL_FAILURE``.
        """
        verification = verify_run(
            run_id=run_id,
            expected_mappings=list(expected_mappings),
            adapter=self._adapter,
            target_calendar_id=target_calendar_id,
            clock=self._clock,
        )
        updated = self._apply_verification(list(expected_mappings), verification)
        if verification.all_verified:
            return WriteResult(
                run_id=run_id,
                status=WriteStatus.SUCCESS,
                reason_code=None,
                written_mappings=tuple(updated),
                verification=verification,
            )
        raise ExternalSyncFailedError(
            f"verification confirmed missing/mismatched events for run {run_id!r}",
            written=tuple(updated),
            verification=verification,
        )

    def _translate_error(
        self, exc: CalendarWriterError, *, run_id: str | None
    ) -> WriteResult:
        """Boundary translation promised by ``errors.py``: each typed
        exception becomes the ``WriteResult`` matching its ``reason_code``,
        preserving any partial-progress state the exception carries.

        ``error`` carries ``str(exc)`` so enriched adapter detail (e.g. the
        Google adapter's "events.list failed ...: HTTP 403" prose) reaches
        the operator instead of collapsing to the bare ``reason_code``.
        Exception messages here are typed error prose only — adapters never
        embed raw calendar content or secrets."""
        reason_code = type(exc).reason_code
        status = (
            WriteStatus.ABORTED_PRE_WRITE
            if reason_code in _ABORT_REASONS
            else WriteStatus.PARTIAL_FAILURE
        )
        return WriteResult(
            run_id=run_id,
            status=status,
            reason_code=reason_code,
            written_mappings=exc.written,
            verification=exc.verification,
            error=str(exc),
        )

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
