# Phase 1: Core Planning Foundation

## Goal

Build the deterministic foundation for onboarding, structured syllabus generation, task planning, validation, state transitions, and draft scheduling. Do not write to calendars in this phase.

## Required Docs

- `../../AGENTS.md`
- `../axioms/01-system-boundaries.md`
- `../axioms/02-state-machine.md`
- `../axioms/03-data-contracts.md`
- `../axioms/04-validation-layer.md`
- `../axioms/05-scheduler-policy.md`
- `../axioms/21-accountability-layer.md`
- `../specs/user-profile.schema.md`
- `../specs/motivation-profile.schema.md`
- `../specs/syllabus-units.schema.md`
- `../specs/task-plan.schema.md`
- `../specs/validation-result.schema.md`
- `../specs/scheduler-output.schema.md`

## Deliverables

- Deterministic Supervisor state machine.
- User profile contract and validation.
- Motivation profile contract and validation.
- Structured syllabus and task plan contracts.
- Validation layer with schema, graph, coverage, user-fit, and scheduling prechecks.
- Pure Scheduler that emits draft schedules or typed failures.
- Fixture set for valid and invalid artifacts.

## Acceptance Criteria

- Invalid Planner output cannot reach Scheduler.
- `task_plan` cannot include `prerequisites_met`.
- Scheduler failures include `reason_code` and debug payload.
- State transition tests cover valid and forbidden paths.
- Active plans are versioned, not mutated in place.

## Explicit Non-Goals

- Calendar writes.
- Approval UI.
- Drift classification.
- RAG ingestion.
- Offline mode.
- Sponsor reporting.
- Advanced RAG.

## Test Expectations

- Contract tests for all Phase 1 schemas.
- Graph validation tests for duplicate IDs, orphan dependencies, cycles, and self-dependencies.
- Scheduler tests for each Phase 1 reason code.
- Supervisor tests for retry exhaustion and `error_requires_user`.
