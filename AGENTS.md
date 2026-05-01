# Agent Constitution

## Project Mission

Build a deterministic career-preparation orchestration engine that turns user goals, availability, and validated learning structure into safe, auditable study plans and calendar drafts.

The product helps users prepare for interviews and career transitions by coordinating what to study, when to study it, how progress is measured, and when plans must be adjusted. It is not a generic chatbot, content site, or autonomous calendar assistant.

## Core Thesis

**LLMs propose. Deterministic infrastructure disposes.**

LLMs may generate structured candidates and user-facing explanations. Deterministic code owns routing, validation, scheduling, approval gates, calendar writes, telemetry, drift classification, retry limits, concurrency locks, and side-effect safety.

## Non-Negotiable Axioms

- No silent calendar writes.
- No LLM-controlled routing.
- No invalid Planner output may reach the Scheduler.
- No calendar write may occur without `approval_event_id`.
- Prerequisites are computed deterministically from dependencies and completion state.
- The active plan is never mutated directly; use plan versions.
- Every failure must produce a typed `reason_code`.
- Every external side effect must support dry-run, verification, and rollback.
- Drift classification is deterministic in the MVP.
- Source confidence is scored deterministically; LLMs do not assign confidence.
- The MVP is always-online for plan mutations and calendar writes; offline task completion is the only allowed offline mutation and must be tagged with `data_quality`.
- Every calendar write must pass an `approved_payload_hash` recheck against the live draft, recomputed under the recorded `hash_canonicalization_version`.
- Validation thresholds, drift thresholds, and source confidence base scores are heuristic priors until calibrated.

## Required Reading Before Major Changes

- Product laws: `docs/axioms/00-product-thesis.md`
- System boundaries: `docs/axioms/01-system-boundaries.md`
- State machine: `docs/axioms/02-state-machine.md`
- Data contracts: `docs/axioms/03-data-contracts.md` and the relevant files in `docs/specs/`
- Validation: `docs/axioms/04-validation-layer.md`
- Scheduler policy: `docs/axioms/05-scheduler-policy.md`
- Calendar safety: `docs/axioms/06-calendar-safety.md`
- Telemetry and drift: `docs/axioms/07-telemetry-and-drift.md`
- RAG source claims: `docs/axioms/08-rag-source-claims.md`
- Cost and metrics: `docs/axioms/09-cost-and-metrics.md`
- MVP roadmap: `docs/axioms/10-mvp-roadmap.md`
- Prerequisite logic: `docs/axioms/11-prerequisite-logic.md`
- Edge-case policy engine: `docs/axioms/12-edge-case-policy-engine.md`
- Concurrency model: `docs/axioms/13-concurrency-model.md`
- Checkpointing: `docs/axioms/14-checkpointing-recovery.md`
- Plan versioning and diffs: `docs/axioms/15-plan-versioning-and-diffs.md`
- Reliability patterns: `docs/axioms/16-reliability-patterns.md`
- Duration estimation: `docs/axioms/17-duration-estimation.md`
- Caching strategy: `docs/axioms/18-caching-strategy.md`
- Always-online MVP and offline completion exception: `docs/axioms/19-always-online-mvp.md`
- Partial syllabus regeneration (Phase 2/3): `docs/axioms/20-partial-syllabus-regeneration.md`
- Accountability layer and sponsor reporting: `docs/axioms/21-accountability-layer.md` and `docs/specs/motivation-profile.schema.md`
- Relevant ADRs in `docs/decisions/`
- The applicable phase plan in `docs/implementation-plans/`
- Required deterministic test scenarios: `docs/golden-test-cases.md`

## Development Rules

- Treat schemas in `docs/specs/` as contracts. Update specs before changing schema-related code.
- Keep LLM outputs structured. Prose can explain decisions but must not be the source of truth for routing, scheduling, validation, or writes.
- Pass all generated plans through deterministic validation before scheduling.
- Write new plan versions instead of editing the active plan in place.
- Preserve typed `reason_code` values across validation, scheduling, telemetry, and user-visible errors.
- Design external integrations with `dry_run`, idempotency keys, verification reads, and rollback paths.
- Keep orchestration state explicit. Do not hide workflow state in prompts, chat history, or calendar event text.
- LLM calls live only inside `StrategistNode`, `PlannerNode`, `ReflectionSummaryNode`, or `UserFacingExplanationNode`.

## Testing Expectations

- State transitions must have tests for valid paths and forbidden paths.
- Validation checks must cover schema failures, graph failures, coverage failures, user-fit failures, and scheduling prechecks.
- Scheduler tests must assert `reason_code` and debug payloads for failures.
- Calendar write tests must cover preview, approval, write, verification, duplicate prevention, and rollback.
- Telemetry and drift tests must prove deterministic classification from recorded events.
- LLM-facing code must be tested with fixtures and contract checks, not by trusting prompt wording.
- The scenarios in `docs/golden-test-cases.md` must be exercised on every commit that touches orchestration.

## Forbidden Shortcuts

- Do not let an LLM decide which node runs next.
- Do not let an LLM mark prerequisites as met.
- Do not write directly to a calendar from Scheduler output.
- Do not write calendar events without `approval_event_id`, `run_id`, `plan_version`, and `task_id`.
- Do not treat invalid structured output as "good enough."
- Do not silently drop validation failures or retries.
- Do not exceed two repair attempts per artifact.
- Do not exceed two Scheduler-Planner iterations.
- Do not mutate `active_plan` directly.
- Do not store raw calendar event titles or descriptions.
- Do not let LLMs assign source confidence in the MVP.
- Do not add offline mode, per-user ML models, silent writes, or autonomous replanning in the MVP.
