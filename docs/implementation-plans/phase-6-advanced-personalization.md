# Phase 6: Advanced Personalization

## Goal

Improve duration predictions, drift response quality, and personalization with opt-in aggregate data, only after the deterministic core and accountability MVP are stable.

This phase is held until Phases 1–5 (and the Phase 7 accountability MVP) are proven in production. It must never compromise the calendar safety or determinism invariants established in earlier phases.

## Required Docs

- `../../AGENTS.md`
- `../axioms/07-telemetry-and-drift.md`
- `../axioms/09-cost-and-metrics.md`
- `../axioms/16-reliability-patterns.md`
- `../axioms/17-duration-estimation.md`
- `../axioms/18-caching-strategy.md`
- `../specs/telemetry.schema.md`
- `../specs/drift-event.schema.md`
- `../decisions/ADR-0004-no-per-user-ml-model-in-mvp.md`

## Deliverables

- Pooled duration model with explicit features (task category, type, cognitive load, experience level, time of day, day of week, recent completion rate, historical category multiplier).
- Opt-in data controls and audit logs.
- Advanced calibration that combines deterministic multipliers with the pooled model.
- More granular user modeling for power users only (200+ completed tasks, 30+ completions per category, multi-week stability).
- Cohort-level retrieval improvements gated behind explicit consent.
- Advanced accountability personalization (pressure-tolerance-aware nudge phrasing, per-user threshold adaptation) layered on top of the deterministic policy engine.

## Acceptance Criteria

- LLMs do not control routing, validation, scheduling, or calendar writes.
- Pooled model output feeds the deterministic Scheduler; it does not replace it.
- All personalization improvements remain explainable through deterministic policy and reason codes.
- Opt-in data controls allow users to view, export, and delete their data.
- Drift classification remains deterministic; advanced models may change duration multipliers but never silently mutate the active plan.
- Per-user models train only when the threshold criteria in `../axioms/17-duration-estimation.md` are met.

## Explicit Non-Goals

- Replacing the deterministic Supervisor with an autonomous agent.
- Allowing LLM-controlled routing or calendar writes.
- Cross-user training without explicit opt-in.
- Treating model output as ground truth.
- Removing approval gates or rollback paths.

## Test Expectations

- Tests prove that personalized estimates respect the deterministic policy table in `../axioms/12-edge-case-policy-engine.md`.
- Tests prove that the calendar safety invariants from `../axioms/06-calendar-safety.md` are preserved.
- Tests prove that opt-out removes the user's data from training and serving paths.
- Tests prove that pooled model failure does not block planning; the system falls back to deterministic multipliers.
- Tests prove that drift classification still produces typed `reason_code` values without LLM judgment.
