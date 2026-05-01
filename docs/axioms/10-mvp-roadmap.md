# 10: MVP Roadmap

The MVP build plan is split across seven phases. Phases 1–2 deliver the deterministic core. Phase 3 adds permissioned sponsor and parent reporting. Phases 4–6 deliver telemetry, RAG quality, and advanced personalization. Phase 7 ships the full accountability MVP.

## Phase 1: Core Planning Foundation

**Goal:** prove structured generation and deterministic validation.

Deliverables:

- User profile schema.
- Motivation profile schema.
- Structured onboarding UI.
- Syllabus schema.
- Task schema.
- `StrategistNode`.
- `PlannerNode`.
- Validation Layer.
- Basic draft plan UI.

Excluded:

- Calendar writes.
- Adaptive replanning.
- Cross-user learning.
- Sponsor reporting.
- Advanced RAG.

See `../implementation-plans/phase-1-core-planning.md`.

## Phase 2: Calendar Safety

**Goal:** safely convert validated tasks into draft schedules and approved calendar events.

Deliverables:

- Calendar free/busy integration.
- Deterministic Scheduler.
- Draft schedule preview.
- Approval gate UI.
- Calendar Write Manager.
- `run_id`/`task_id` metadata.
- Local event mapping.
- Write verification and rollback.

See `../implementation-plans/phase-2-calendar-safety.md`.

## Phase 3: Sponsor and Parent Reporting

**Goal:** support optional accountability through permissioned sponsor visibility.

Deliverables:

- Sponsor entity model.
- Sponsor invite flow.
- Sponsor permission levels.
- Sponsor report schema.
- Sponsor report approval gate.
- Weekly sponsor summary.
- Report delivery logs.
- Privacy filter for disallowed content.

Excluded:

- Live parent surveillance dashboard.
- Raw calendar sharing.
- Essay draft sharing by default.
- Sponsor control over the user's plan without user approval.

See `../implementation-plans/phase-3-sponsor-reporting.md`.

## Phase 4: Telemetry and Calibration

**Goal:** improve estimates based on execution.

Deliverables:

- Completion telemetry logger.
- Actual vs predicted duration tracking.
- User category multipliers.
- Simple drift classifier.
- Accountability effectiveness metrics.
- Replan suggestion flow.

See `../implementation-plans/phase-4-telemetry-drift.md`.

## Phase 5: RAG Quality and Caching

**Goal:** improve curriculum quality with structured evidence.

Deliverables:

- Claim store.
- Source type classification.
- Confidence scoring.
- Expiration policy.
- Company interview pattern cache.
- Topic module cache.
- Admissions / application milestone templates.

See `../implementation-plans/phase-5-rag-caching.md`.

## Phase 6: Advanced Personalization

**Goal:** improve predictions with opt-in aggregate data, only after the deterministic core is stable.

Deliverables:

- Pooled duration model.
- Opt-in data controls.
- Advanced calibration.
- More granular user modeling.
- Advanced accountability personalization.

See `../implementation-plans/phase-6-advanced-personalization.md`.

## Phase 7: Accountability MVP

**Goal:** prove that accountability improves execution without damaging trust.

Deliverables:

- Accountability contract schema.
- Weekly check-in flow.
- Completion dashboard.
- Missed-task detection.
- Behind-schedule percentage.
- Deterministic accountability policy engine.
- Private user nudges.
- Recovery-plan draft flow.
- User recommitment flow.

Excluded:

- Parent or sponsor reporting by default (handled in Phase 3 only with explicit opt-in).
- Financial penalties.
- AI therapy or personality diagnosis.
- Fully autonomous replanning.

See `../implementation-plans/phase-7-accountability-mvp.md`.

## Explicitly Out of Scope (MVP)

- Offline mode (except the narrow offline task-completion exception in `19-always-online-mvp.md`).
- Silent calendar writes.
- Silent parent or sponsor reporting.
- Per-user ML models.
- Cross-user training without opt-in.
- Autonomous replanning without approval.
- Complex multi-calendar conflict resolution beyond core free/busy.
- General-purpose autonomous agent behavior.
- Unbounded planner-scheduler loops.
- Parent surveillance dashboards.
- Financial penalties or deposit-based commitment contracts.
- AI therapy or mental-health coaching.

## Sequencing Rationale

The MVP must prove five things before advancing to Phase 6 and beyond:

1. The system can generate a useful structured syllabus.
2. The system can convert that syllabus into valid task plans.
3. The system can schedule tasks safely without calendar mistakes.
4. Users are willing to approve and follow the generated schedule.
5. Accountability interventions increase completion without damaging user trust.

If those five things work, adaptive replanning, sponsor reporting at scale, RAG quality, and personalization become valuable. If they do not work, more agentic complexity will only make the system harder to trust.

## Related Docs

- `00-product-thesis.md`
- `06-calendar-safety.md`
- `09-cost-and-metrics.md`
- `21-accountability-layer.md`
- `../implementation-plans/`
- `../risks-and-mitigations.md`
