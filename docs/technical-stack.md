# Recommended Technical Stack

This stack is the recommended baseline for the MVP. Specific version pins are deferred to implementation; the components named here align with the deterministic-first architecture.

## Backend

- **Python** as the primary language.
- **FastAPI** for HTTP endpoints.
- **Pydantic** for schema enforcement at boundaries.
- **LangGraph** or an equivalent state machine for the deterministic Supervisor and orchestration graph.
- **PostgreSQL** for durable state, plan versions, telemetry, mappings, and audit logs.
- **Redis** or an equivalent queue system for background jobs and locks.
- **Google Calendar API** as the first calendar provider.

## LLM Layer

- **Stronger model** for `StrategistNode` (curriculum quality matters most here).
- **Cheaper structured-output model** for `PlannerNode`.
- **Cheap model** for `ReflectionSummaryNode` and `UserFacingExplanationNode`.
- **Strict JSON schema or function calling** for every LLM call.

LLM adapters are limited to four named nodes (`axioms/01-system-boundaries.md`). All other code paths must be deterministic.

## Frontend

- **React** or **Next.js**.
- Schedule preview UI.
- Approval gate UI.
- Plan diff UI (deterministic diff rendered in approval flow).
- Task completion UI.
- Metrics dashboard for operational and quality metrics.

## Database Tables

Recommended tables:

- `users`
- `user_profiles`
- `motivation_profiles`
- `accountability_contracts`
- `sponsors`
- `sponsor_permissions`
- `source_claims`
- `syllabus_versions`
- `plan_versions`
- `tasks`
- `draft_schedules`
- `calendar_event_mappings`
- `approval_events`
- `telemetry_events`
- `checkin_events`
- `accountability_events`
- `sponsor_reports`
- `notification_logs`
- `drift_events`
- `checkpoints`

Each table has a corresponding canonical schema in `specs/` where applicable. Motivation, sponsor, and accountability schemas live under `specs/motivation-profile.schema.md` and `axioms/21-accountability-layer.md`.

## Operational Components

- Background workers for calendar sync, telemetry processing, and drift classification.
- Logging and tracing aligned to typed `reason_code` values.
- Embedding refresh jobs for RAG retrieval.
- Cache layer for RAG results, company patterns, and topic modules (`axioms/18-caching-strategy.md`).
- Cost dashboards aligned to the targets in `axioms/09-cost-and-metrics.md`.

## What This Stack Excludes (MVP)

- Offline data layers (`axioms/19-always-online-mvp.md`).
- Per-user ML training infrastructure (`decisions/ADR-0004-no-per-user-ml-model-in-mvp.md`).
- Cross-user training pipelines without explicit opt-in.
- Generic autonomous agent frameworks that hide routing inside prompts.

## Related Docs

- `axioms/01-system-boundaries.md`
- `axioms/06-calendar-safety.md`
- `axioms/09-cost-and-metrics.md`
- `axioms/16-reliability-patterns.md`
- `axioms/18-caching-strategy.md`
- `axioms/19-always-online-mvp.md`
- `axioms/21-accountability-layer.md`
- `specs/motivation-profile.schema.md`
