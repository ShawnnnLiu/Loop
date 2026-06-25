"""The single canonical (state, signal) → next-state table.

Modifying the table is the only way to change supervisor routing; the
``route()`` function in ``routing.py`` is a pure dictionary lookup, so
adding a new transition is a one-line change here. The mirror set of tests
in ``tests/supervisor/test_transitions.py`` exercises every valid transition
and asserts that every other (state, signal) pair is forbidden.
"""

from __future__ import annotations

from collections.abc import Mapping

from .state import SupervisorSignal as Sig
from .state import SupervisorState as S

TRANSITIONS: Mapping[tuple[S, Sig], S] = {
    # ---- INITIAL ----
    (S.INITIAL, Sig.USER_PROFILE_COLLECTED): S.STRATEGIST_RUNNING,

    # ---- COLLECTING_USER_PROFILE (Phase 2+) ----
    (S.COLLECTING_USER_PROFILE, Sig.USER_PROFILE_COLLECTED): S.STRATEGIST_RUNNING,

    # ---- STRATEGIST ----
    (S.STRATEGIST_RUNNING, Sig.STRATEGIST_OUTPUT_PRODUCED): S.STRATEGIST_VALIDATING,
    (S.STRATEGIST_VALIDATING, Sig.VALIDATION_PASSED): S.PLANNER_RUNNING,
    (S.STRATEGIST_VALIDATING, Sig.VALIDATION_FAILED_REPAIRABLE): S.STRATEGIST_RUNNING,
    (S.STRATEGIST_VALIDATING, Sig.REPAIR_LIMIT_EXCEEDED): S.ERROR_REQUIRES_USER,

    # ---- PLANNER ----
    (S.PLANNER_RUNNING, Sig.PLANNER_OUTPUT_PRODUCED): S.PLANNER_VALIDATING,
    (S.PLANNER_VALIDATING, Sig.VALIDATION_PASSED): S.SCHEDULER_RUNNING,
    (S.PLANNER_VALIDATING, Sig.VALIDATION_FAILED_REPAIRABLE): S.PLANNER_RUNNING,
    (S.PLANNER_VALIDATING, Sig.REPAIR_LIMIT_EXCEEDED): S.ERROR_REQUIRES_USER,

    # ---- SCHEDULER ----
    (S.SCHEDULER_RUNNING, Sig.SCHEDULER_SUCCESS): S.AWAITING_USER_APPROVAL,
    (S.SCHEDULER_RUNNING, Sig.SCHEDULER_PARTIAL_FAILURE): S.PLANNER_RUNNING,
    (S.SCHEDULER_RUNNING, Sig.SCHEDULER_FULL_FAILURE): S.PLANNER_RUNNING,
    (S.SCHEDULER_RUNNING, Sig.REPAIR_LIMIT_EXCEEDED): S.ERROR_REQUIRES_USER,

    # ---- APPROVAL (Phase 2) ----
    (S.AWAITING_USER_APPROVAL, Sig.USER_APPROVED): S.CALENDAR_WRITE_APPROVED,
    (S.AWAITING_USER_APPROVAL, Sig.USER_REJECTED): S.TERMINAL_DISCARDED,

    # ---- DROP (completion/drop memory) ----
    # A deterministic drop produces a survivors-only draft and routes a fresh run
    # straight to approval — no scheduler (survivors keep their placements). The
    # approval + delete-only write gate still applies (no silent write); on
    # reject the fresh run discards and the active plan is untouched.
    (S.INITIAL, Sig.DROP_REQUESTED): S.AWAITING_USER_APPROVAL,

    # ---- CALENDAR WRITE (Phase 2) ----
    # Pre-write gates can fail before the adapter is touched (lock busy,
    # hash mismatch); both route to the failure-handling state so rollback
    # can be requested by the operator.
    (S.CALENDAR_WRITE_APPROVED, Sig.CALENDAR_WRITE_STARTED): S.CALENDAR_WRITE_IN_PROGRESS,
    (S.CALENDAR_WRITE_APPROVED, Sig.CALENDAR_WRITE_FAILED): S.CALENDAR_WRITE_FAILED_STATE,

    (S.CALENDAR_WRITE_IN_PROGRESS, Sig.CALENDAR_WRITE_SUCCEEDED): S.CALENDAR_WRITE_VERIFIED,
    (S.CALENDAR_WRITE_IN_PROGRESS, Sig.CALENDAR_VERIFICATION_FAILED): S.CALENDAR_WRITE_FAILED_STATE,
    (S.CALENDAR_WRITE_IN_PROGRESS, Sig.CALENDAR_WRITE_FAILED): S.CALENDAR_WRITE_FAILED_STATE,

    # A verified write activates the plan (Phase 4). The journey no longer ends
    # at the write — the plan lives on as ACTIVE_PLAN and accrues telemetry.
    (S.CALENDAR_WRITE_VERIFIED, Sig.PLAN_ACTIVATED): S.ACTIVE_PLAN,

    # Failed writes self-loop while rollback runs, then exit to user attention.
    (S.CALENDAR_WRITE_FAILED_STATE, Sig.CALENDAR_ROLLBACK_REQUESTED): S.CALENDAR_WRITE_FAILED_STATE,
    (S.CALENDAR_WRITE_FAILED_STATE, Sig.CALENDAR_ROLLBACK_COMPLETED): S.ERROR_REQUIRES_USER,

    # ---- ACTIVE PLAN / DRIFT / REPLAN LOOP (Phase 4, axiom 07) ----
    # Deterministic drift classification drives these signals; an LLM never
    # chooses them. A required replan re-enters PLANNER_RUNNING so it flows
    # through validation → scheduler → approval — the approval gate is never
    # bypassed (no calendar write without approval). The absence of any
    # ACTIVE_PLAN/DRIFT_DETECTED/REPLAN_REQUIRED → CALENDAR_WRITE_* edge is the
    # enforcement of axiom 02's invalid-transition table.
    (S.ACTIVE_PLAN, Sig.DRIFT_DETECTED): S.DRIFT_DETECTED,
    (S.ACTIVE_PLAN, Sig.NO_DRIFT): S.ACTIVE_PLAN,
    (S.ACTIVE_PLAN, Sig.PLAN_COMPLETED): S.TERMINAL_SUCCESS,

    (S.DRIFT_DETECTED, Sig.REPLAN_REQUIRED): S.REPLAN_REQUIRED,
    (S.DRIFT_DETECTED, Sig.REPLAN_NOT_REQUIRED): S.ACTIVE_PLAN,

    (S.REPLAN_REQUIRED, Sig.REPLAN_STARTED): S.PLANNER_RUNNING,

    # ---- TYPED PANIC (axiom 16) ----
    # Every non-terminal state takes UNRECOVERABLE_ERROR straight to user
    # attention. Deterministic node wrappers emit it when a node fails in a
    # way no repair loop covers (unexpected exception, corrupted artifact) —
    # the typed escape hatch that keeps "crashed" from becoming an implicit,
    # unroutable state. Terminal states and ERROR_REQUIRES_USER itself stay
    # sinks.
    **{
        (state, Sig.UNRECOVERABLE_ERROR): S.ERROR_REQUIRES_USER
        for state in S
        if state
        not in (S.TERMINAL_SUCCESS, S.TERMINAL_DISCARDED, S.ERROR_REQUIRES_USER)
    },
}
"""All allowed (state, signal) → next-state edges.

Anything not in this map is forbidden by the routing function. Terminal
states (``TERMINAL_SUCCESS``, ``TERMINAL_DISCARDED``) and
``ERROR_REQUIRES_USER`` deliberately have no outgoing transitions.
"""


VALID_SIGNALS_BY_STATE: dict[S, set[Sig]] = {}
for (state, signal), _next in TRANSITIONS.items():
    VALID_SIGNALS_BY_STATE.setdefault(state, set()).add(signal)
