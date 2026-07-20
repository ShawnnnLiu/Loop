# Documentation Index

This repo uses documentation as the stable axiom base for future implementation work. The technical report is the source of truth; every doc here must align with it.

Core thesis: **LLMs propose. Deterministic infrastructure disposes.**

## Sections

- `docs/axioms/` — Stable product laws and engineering constraints. Start here before designing behavior.
- `docs/specs/` — Data contracts for structured objects exchanged between nodes and deterministic services.
- `docs/decisions/` — Architecture decision records that explain irreversible or high-cost choices.
- `docs/implementation-plans/` — Phased build plans with deliverables, acceptance criteria, non-goals, and tests.
- `docs/writeups/` — Engineering writeups over completed, measured work (numbers trace to committed artifacts).
- `docs/golden-test-cases.md` — Required deterministic test scenarios.
- `docs/risks-and-mitigations.md` — Risk register and cross-cutting mitigations.
- `docs/technical-stack.md` — Recommended stack for the MVP.
- `docs/open-questions.md` — Tracked product questions.
- `.cursor/rules/` — Always-on Cursor behavior for agents working in this repo.

## Axioms

1. `00-product-thesis.md` — Product thesis, target user, MVP direction.
2. `01-system-boundaries.md` — Allowed LLM nodes and deterministic ownership.
3. `02-state-machine.md` — Plan states, Supervisor pseudocode, mutability rules.
4. `03-data-contracts.md` — Major objects, producers, consumers, contract rules.
5. `04-validation-layer.md` — Schema, graph, coverage, user-fit checks; repair policy.
6. `05-scheduler-policy.md` — Inputs, constraints, ordering, reason codes, debug payloads.
7. `06-calendar-safety.md` — Approval gates, write flow, verification, rollback.
8. `07-telemetry-and-drift.md` — Privacy rules, drift triggers, drift responses.
9. `08-rag-source-claims.md` — Claim schema, source types, confidence formula, expiration.
10. `09-cost-and-metrics.md` — Cost targets, controls, success metrics.
11. `10-mvp-roadmap.md` — Eight-phase build plan and explicit out-of-scope items.
12. `11-prerequisite-logic.md` — Deterministic prerequisite computation.
13. `12-edge-case-policy-engine.md` — Policy table, profile update policy, staleness triggers.
14. `13-concurrency-model.md` — Calendar write lock, draft promotion, race rules.
15. `14-checkpointing-recovery.md` — Checkpoint timing, mid-node crash, fork semantics.
16. `15-plan-versioning-and-diffs.md` — Versioning rules and deterministic diff schema.
17. `16-reliability-patterns.md` — Typed reason codes, dry-run, rollback, invariant checker.
18. `17-duration-estimation.md` — Phase 1 heuristics through Phase 4 per-user models.
19. `18-caching-strategy.md` — What to cache, invalidation triggers, cache keys.
20. `19-always-online-mvp.md` — Online-only scope, offline behavior rules, and the offline task-completion exception.
21. `20-partial-syllabus-regeneration.md` — Phase 2/3 deterministic patch-vs-regenerate classifier.
22. `21-accountability-layer.md` — Deterministic accountability policy engine, weekly check-ins, and sponsor reporting.
23. `22-llm-evaluation-and-observability.md` — LLM eval harness, structured-generation contract, generation reason codes, per-call observability.

## Specs

- `specs/user-profile.schema.md`
- `specs/motivation-profile.schema.md`
- `specs/source-claim.schema.md`
- `specs/syllabus-units.schema.md`
- `specs/task-plan.schema.md`
- `specs/validation-result.schema.md`
- `specs/scheduler-output.schema.md`
- `specs/approval-event.schema.md`
- `specs/calendar-event-mapping.schema.md`
- `specs/telemetry.schema.md`
- `specs/drift-event.schema.md`
- `specs/checkpoint.schema.md`
- `specs/plan-diff.schema.md`

## Decisions

- `decisions/ADR-0001-deterministic-control-plane.md`
- `decisions/ADR-0002-preview-only-calendar-writes.md`
- `decisions/ADR-0003-no-offline-mode-in-mvp.md`
- `decisions/ADR-0004-no-per-user-ml-model-in-mvp.md`
- `decisions/ADR-0005-structured-syllabus-not-prose.md`
- `decisions/ADR-0006-llm-never-touches-the-calendar.md`

## Implementation Plans

See `implementation-plans/README.md` for the index. Active plans live at the
top level of `implementation-plans/`; completed plans are archived under
`implementation-plans/completed/`.

## Reading Path

1. Read `AGENTS.md`.
2. Read `axioms/00-product-thesis.md` through `axioms/06-calendar-safety.md`.
3. Read the relevant schema in `specs/`.
4. Read `axioms/11-prerequisite-logic.md` through `axioms/21-accountability-layer.md` as needed.
5. Check related ADRs in `decisions/`.
6. Use the relevant phase plan from `implementation-plans/`.
7. Cross-check tests against `golden-test-cases.md`.

Do not implement product code from memory. Anchor changes in the contracts and invariants documented here.
