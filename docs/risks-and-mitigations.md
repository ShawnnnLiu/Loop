# Risks and Mitigations

## Risk Register

| Risk | Why It Matters | Mitigation |
| --- | --- | --- |
| LLM produces invalid tasks | Bad tasks corrupt the schedule | Strict validation and bounded repair (`axioms/04-validation-layer.md`) |
| Calendar duplicates | Damages user trust | `run_id`/`task_id` idempotency, dedup-by-metadata (`axioms/06-calendar-safety.md`) |
| Bad schedule quality | User rejects the product | Draft preview, manual edits, clear repair options (`axioms/05-scheduler-policy.md`) |
| Overfitting personalization | Bad estimates from sparse data | Deterministic multipliers first, model only at scale (`axioms/17-duration-estimation.md`) |
| Privacy concerns | Calendar and progress data are sensitive | Minimum telemetry and no raw calendar titles (`axioms/07-telemetry-and-drift.md`) |
| RAG unreliability | Bad curriculum from low-quality sources | Source scoring, expiration, corroboration (`axioms/08-rag-source-claims.md`) |
| Scope creep | Slows MVP | Exclude offline mode, advanced ML, and autonomous replanning in MVP (`axioms/10-mvp-roadmap.md`, `axioms/19-always-online-mvp.md`) |
| Silent calendar write | Trust-breaking event | Explicit approval gate invariant (`axioms/06-calendar-safety.md`) |
| Silent sponsor reporting | Trust-breaking event | Explicit sponsor permission and report approval (`axioms/21-accountability-layer.md`) |
| Parent surveillance | User may feel controlled or exposed | Summary-only default, revocable permissions, no live dashboards (`axioms/21-accountability-layer.md`) |
| Motivational overreach | AI may feel manipulative or judgmental | Use behavioral telemetry, not psychological labels (`axioms/07-telemetry-and-drift.md`) |
| Infinite agent loop | Cost and reliability issue | Hard retry caps, 2 repair attempts, 2 Scheduler-Planner iterations (`axioms/04-validation-layer.md`, `axioms/09-cost-and-metrics.md`) |
| User manually edits event | App may overwrite user intent | Detect and preserve `user_modified_bool` (`specs/calendar-event-mapping.schema.md`) |
| Financial penalty complexity | Legal, ethical, and support risk | Exclude deposits and penalties from MVP (`axioms/00-product-thesis.md`, `axioms/10-mvp-roadmap.md`) |
| Sponsor visibility violation | Private information could be exposed | Deterministic privacy filter and report schema validation (`axioms/21-accountability-layer.md`) |

## Cross-Cutting Mitigations

- Every failure carries a typed `reason_code` (`axioms/16-reliability-patterns.md`).
- Every external side effect supports dry-run, verification, and rollback (`axioms/16-reliability-patterns.md`).
- The active plan is never mutated directly; new work creates a new plan version (`axioms/15-plan-versioning-and-diffs.md`).
- LLMs are restricted to four adapter nodes (`axioms/01-system-boundaries.md`).
- Drift classification is deterministic in the MVP (`axioms/07-telemetry-and-drift.md`).
- Concurrency is enforced by `calendar_write_lock` (`axioms/13-concurrency-model.md`).

## What Increases Risk

- Letting an LLM decide routing.
- Letting an LLM decide whether an intervention or sponsor report fires.
- Skipping validation between Planner and Scheduler.
- Writing to the calendar without `approval_event_id`.
- Sending sponsor reports without an approved permission and report approval.
- Mutating the active plan in place.
- Storing raw calendar event titles or descriptions.
- Storing psychological labels derived from telemetry.
- Adding offline mode before the online flow is reliable.
- Allowing more than 2 repair attempts for any artifact.

## Related Docs

- `axioms/00-product-thesis.md`
- `axioms/01-system-boundaries.md`
- `axioms/04-validation-layer.md`
- `axioms/06-calendar-safety.md`
- `axioms/07-telemetry-and-drift.md`
- `axioms/16-reliability-patterns.md`
- `axioms/21-accountability-layer.md`
- `specs/motivation-profile.schema.md`
- `golden-test-cases.md`
