# ADR-0004: No Per-User ML Model in MVP

## Status

Accepted

## Context

The product needs personalization, but per-user ML models introduce training data requirements, privacy concerns, infrastructure cost, and hard-to-debug behavior before the core loop is proven.

## Decision

The MVP uses heuristic duration estimates, deterministic drift triggers, and simple category multipliers first. No per-user ML model is trained or served in the MVP.

## Consequences

Personalization is less sophisticated at first, but behavior remains explainable and cheap. Telemetry can later justify more advanced approaches if deterministic calibration is insufficient.

## Related Docs

- `../axioms/07-telemetry-and-drift.md`
- `../axioms/09-cost-and-metrics.md`
- `../specs/telemetry.schema.md`
