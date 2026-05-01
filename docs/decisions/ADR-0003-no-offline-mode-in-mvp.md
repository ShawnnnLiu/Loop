# ADR-0003: No Offline Mode in MVP

## Status

Accepted

## Context

Offline mode adds local-first storage, sync reconciliation, calendar conflict handling, and multi-device merge complexity. Those concerns would distract from proving deterministic planning and calendar safety.

## Decision

The MVP is always-online. Planning, approval, calendar writes, verification, telemetry, and drift classification require server-authoritative state.

## Consequences

Users need connectivity for core workflows. In exchange, the MVP avoids ambiguous sync state and can enforce approval, versioning, and rollback invariants centrally.

## Related Docs

- `../axioms/10-mvp-roadmap.md`
- `../axioms/06-calendar-safety.md`
- `../implementation-plans/phase-1-core-planning.md`
