# Phase 4: Telemetry and Drift

## Goal

Capture privacy-first task telemetry and classify plan drift deterministically so the system can recommend safe replanning.

## Required Docs

- `../../AGENTS.md`
- `../axioms/07-telemetry-and-drift.md`
- `../axioms/09-cost-and-metrics.md`
- `../specs/telemetry.schema.md`
- `../specs/drift-event.schema.md`
- `../decisions/ADR-0004-no-per-user-ml-model-in-mvp.md`

## Deliverables

- Telemetry event ingestion for completion, duration, and reschedule counts.
- Deterministic drift classifier.
- Drift evidence payloads.
- Duration calibration using simple category multipliers.
- Accountability effectiveness metrics (completion lift, recovery acceptance, sponsor opt-in rates).
- Metrics for completion rate, duration error, and schedule edit rate.

## Acceptance Criteria

- Drift events include `drift_type`, `reason_code`, evidence, and recommended action.
- Drift classification does not call an LLM in the MVP.
- Replanning recommendations do not modify calendar events without approval.
- Median duration estimate error can be computed from telemetry.
- Privacy review confirms no raw private calendar descriptions are required.

## Explicit Non-Goals

- Per-user ML model.
- Cross-user training without opt-in.
- Autonomous calendar changes.
- Raw calendar content analytics.

## Test Expectations

- Trigger tests for every drift type.
- Boundary tests for threshold values.
- Telemetry schema tests for completed and incomplete tasks.
- Calibration tests for deterministic multiplier application.
- Metrics tests for two-week completion rate.
