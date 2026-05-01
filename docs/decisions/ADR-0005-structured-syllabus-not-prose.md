# ADR-0005: Structured Syllabus, Not Prose

## Status

Accepted

## Context

A prose syllabus is hard to validate, schedule, diff, cache, and connect to source claims. The system needs modules, outcomes, priorities, dependencies, and provenance.

## Decision

`StrategistNode` must output structured syllabus units, not raw prose. Prose summaries may be generated for users, but deterministic consumers use `syllabus_units`.

## Consequences

Prompts and validators must be stricter. In return, the Planner can generate tasks from stable units, validators can check coverage, and RAG claims can remain auditable.

## Related Docs

- `../axioms/03-data-contracts.md`
- `../axioms/08-rag-source-claims.md`
- `../specs/syllabus-units.schema.md`
