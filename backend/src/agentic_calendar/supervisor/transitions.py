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

    # ---- APPROVAL (Phase 2 wiring; declared so transitions are complete) ----
    (S.AWAITING_USER_APPROVAL, Sig.USER_APPROVED): S.WRITING_TO_CALENDAR,
    (S.AWAITING_USER_APPROVAL, Sig.USER_REJECTED): S.TERMINAL_DISCARDED,

    # ---- CALENDAR (Phase 2 wiring) ----
    (S.WRITING_TO_CALENDAR, Sig.CALENDAR_WRITE_SUCCEEDED): S.TERMINAL_SUCCESS,
    (S.WRITING_TO_CALENDAR, Sig.CALENDAR_WRITE_FAILED): S.ERROR_REQUIRES_USER,
}
"""All allowed (state, signal) → next-state edges.

Anything not in this map is forbidden by the routing function. Terminal
states (``TERMINAL_SUCCESS``, ``TERMINAL_DISCARDED``) and
``ERROR_REQUIRES_USER`` deliberately have no outgoing transitions.
"""


VALID_SIGNALS_BY_STATE: dict[S, set[Sig]] = {}
for (state, signal), _next in TRANSITIONS.items():
    VALID_SIGNALS_BY_STATE.setdefault(state, set()).add(signal)
