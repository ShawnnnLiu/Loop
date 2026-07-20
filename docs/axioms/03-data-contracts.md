# 03: Data Contracts

## Principle

Structured objects are the boundary between LLM proposals and deterministic infrastructure. Prompts may produce candidates, but schemas and validators decide whether objects can move forward.

The schemas in `../specs/` are the canonical contracts between LLM nodes and deterministic services. Update the relevant spec before changing object shape or semantics.

## Major Objects

- `user_profile` — User goal, role target, constraints, availability, preferences, and capacity. See `../specs/user-profile.schema.md`.
- `resume_intake_input` — validated bundle handed to the ResumeIntakeNode. See `../specs/resume-intake-input.schema.md`.
- `resume_extraction` — schema-bound proposal returned by the ResumeIntakeNode. See `../specs/resume-extraction.schema.md`.
- `pathway_template` - Curated narrative pathway with evidence slots; a deterministic registry literal, never LLM-authored. See `../specs/pathway-template.schema.md`.
- `pathway_selection` - The user's explicit pathway choice, pinned to a pathway registry version. See `../specs/pathway-selection.schema.md`.
- `source_claim` — Atomic claim from an external or internal source with provenance, deterministic confidence score, and expiration. See `../specs/source-claim.schema.md`.
- `syllabus_units` — Structured learning modules with outcomes, priority, difficulty, and source claims. See `../specs/syllabus-units.schema.md`.
- `task_plan` — Concrete tasks derived from syllabus units. Must not include `prerequisites_met`. See `../specs/task-plan.schema.md`.
- `validation_result` — Deterministic pass/fail result with typed violations and repair payloads. See `../specs/validation-result.schema.md`.
- `scheduler_output` — Draft schedule or scheduling failure with `reason_code` and debug payload. See `../specs/scheduler-output.schema.md`.
- `approval_event` — User approval or rejection of a specific hashed payload. See `../specs/approval-event.schema.md`.
- `calendar_event_mapping` — Mapping between internal tasks and external calendar events. See `../specs/calendar-event-mapping.schema.md`.
- `telemetry_event` — Privacy-first record of task completion, timing, edits, and scheduling friction. See `../specs/telemetry.schema.md`.
- `drift_event` — Deterministic classification that a plan no longer fits observed behavior or calendar reality. See `../specs/drift-event.schema.md`.
- `checkpoint` — Persisted system state for resume after failure. See `../specs/checkpoint.schema.md`.
- `plan_diff` — Deterministic diff between two plan versions. See `../specs/plan-diff.schema.md`.

## Producer and Consumer Map

| Object | Producer | Consumers |
| --- | --- | --- |
| `user_profile` | Onboarding UI, profile service | StrategistNode, validators, Scheduler, drift classifier |
| `resume_intake_input` | app layer (extract request) | ResumeIntakeNode |
| `resume_extraction` | ResumeIntakeNode | onboarding UI (display + edit), tests |
| `pathway_template` | pathway registry (deterministic literals) | onboarding UI (pathway cards), `narrative/` kernel, Strategist constraints composition |
| `pathway_selection` | onboarding UI / Tuning via the `POST /api/onboard` confirm gate | profile service, `narrative/` kernel, Strategist constraints composition |
| `source_claim` | RAG ingestion, claim extractor, deterministic scorer | StrategistNode, syllabus validator, cache, audit views |
| `syllabus_units` | StrategistNode | syllabus validator, PlannerNode, coverage metrics |
| `task_plan` | PlannerNode | task validator, Scheduler, approval UI |
| `validation_result` | validation layer | Supervisor, repair loop, user-facing errors |
| `scheduler_output` | Scheduler | approval UI, Calendar Write Manager |
| `approval_event` | approval UI | Calendar Write Manager, audit log |
| `calendar_event_mapping` | Calendar Write Manager | verifier, rollback, telemetry |
| `telemetry_event` | task UI, calendar sync, completion flow | drift classifier, metrics, calibration |
| `drift_event` | drift classifier | Supervisor, replan flow, explanation node |
| `checkpoint` | checkpointing layer | recovery, audit, fork operations |
| `plan_diff` | diff service | approval UI, replan flow, audit |

## Contract Rules

- Each object has one canonical schema in `../specs/`.
- Every object crossing a node boundary must carry `run_id` where applicable.
- Every failure must include a typed `reason_code`.
- Consumers must not infer missing fields from prompt text.
- Deterministic consumers must reject unknown critical fields if they alter behavior.
- `task_plan.prerequisites_met` is forbidden. Compute prerequisite status deterministically (see `11-prerequisite-logic.md`).
- The active plan is never mutated directly; create a new plan version (see `15-plan-versioning-and-diffs.md`).
- Validation must not mutate the artifact under test.

## Spec-First Development

Treat the schemas as contracts. When changing schema-related code:

1. Update the relevant spec in `../specs/` first.
2. Add or update invalid fixtures alongside valid fixtures.
3. Update validation tests to exercise both shapes.
4. Only then change producer or consumer code.

## Related Docs

- `04-validation-layer.md`
- `05-scheduler-policy.md`
- `11-prerequisite-logic.md`
- `15-plan-versioning-and-diffs.md`
- `../specs/`
