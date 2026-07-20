# Phase 7: Accountability MVP

Status: **complete** — implemented and merged to `main`.

## Goal

Prove that accountability improves execution without damaging trust. The system uses observable behavior — missed tasks, reschedule counts, behind-schedule percentage, check-in completion — as deterministic inputs to the Accountability Policy Engine. Wording may come from an LLM; triggers, permissions, and actions do not.

## Required Docs

- `../../../AGENTS.md`
- `../../axioms/04-validation-layer.md`
- `../../axioms/06-calendar-safety.md`
- `../../axioms/07-telemetry-and-drift.md`
- `../../axioms/12-edge-case-policy-engine.md`
- `../../axioms/15-plan-versioning-and-diffs.md`
- `../../axioms/16-reliability-patterns.md`
- `../../axioms/21-accountability-layer.md`
- `../../specs/motivation-profile.schema.md`
- `../../specs/telemetry.schema.md`

## Deliverables

- Accountability contract schema (derived from the motivation profile).
- Weekly check-in flow and schema (`checkin_events`).
- Completion dashboard (internal view of `completion_rate_7d`, `behind_schedule_percent`, missed tasks).
- Missed-task detection running off `telemetry_events`.
- Behind-schedule percentage computed deterministically.
- Deterministic Accountability Policy Engine (rule-based, ordered, auditable).
- Private user nudges with quiet-hours and channel preferences respected.
- Recovery-plan draft flow that routes through validation, diff, and approval (never in-place mutation).
- User recommitment flow (explicit re-approval of plan, timeline, or intensity).

## Acceptance Criteria

- Every intervention has a typed `reason_code` from the accountability reason code set in `16-reliability-patterns.md`.
- No accountability intervention mutates the task graph or active plan directly; recovery plans create new plan versions.
- Weekly check-ins are generated based on motivation profile cadence and produce `CHECKIN_DUE` / `CHECKIN_MISSED`.
- Private nudges respect `nudge_channel_preference` and `quiet_hours` with zero violations in tests.
- The policy engine is deterministic: the same inputs produce the same action, and every rule evaluation is logged.
- Disabling the accountability contract emits `ACCOUNTABILITY_CONTRACT_INACTIVE` and stops further interventions without breaking the active plan.
- The drift classifier may emit `accountability_mismatch` or `sponsor_pressure_mismatch`; the policy engine (not the LLM) decides the response.
- No psychological labels are stored (`07-telemetry-and-drift.md` §19B.5).

## Explicit Non-Goals

- Parent or sponsor reporting by default (Phase 3 handles opt-in sponsor reports only).
- Financial penalties or deposit-based commitment contracts.
- AI therapy or personality diagnosis.
- Fully autonomous replanning.
- Silent escalation to any external party.

## Test Expectations

- Golden scenarios 16, 21, 22, 23, 24 in `../../golden-test-cases.md`.
- Unit tests for each policy rule with pass and fail cases.
- Deterministic replay tests proving the same telemetry produces the same intervention sequence.
- Recovery-plan tests that prove the draft goes through validation and approval before any calendar change.
- Quiet-hours and channel-preference tests for nudge delivery.
- Audit log tests for every triggered intervention.
