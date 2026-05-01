# ADR-0001: Deterministic Control Plane

## Status

Accepted

## Context

The system uses LLMs to propose syllabus units, task plans, summaries, and explanations. Those outputs are useful but probabilistic. Routing, validation, scheduling, approvals, side effects, telemetry, and retries must be auditable and repeatable.

## Decision

LLMs cannot control routing or side effects. A deterministic Supervisor owns state transitions. Deterministic services own validation, scheduling, calendar writes, drift classification, confidence scoring, and retry limits.

## Consequences

This reduces autonomy but increases safety and debuggability. LLM prompts can improve candidate quality, but correctness must come from schemas, validators, state machines, and tests.

## Related Docs

- `../axioms/00-product-thesis.md`
- `../axioms/01-system-boundaries.md`
- `../axioms/02-state-machine.md`
