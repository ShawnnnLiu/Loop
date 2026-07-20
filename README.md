# Agentic Calendar

Deterministic career-preparation orchestration engine.

> **LLMs propose. Deterministic infrastructure disposes.**

This repository is the source code for the system described under `docs/`. Read
`AGENTS.md` and the relevant axioms in `docs/axioms/` before making any
substantive change.

## Repository layout

```
Agentic-Calendar/
├── AGENTS.md                # constitution; required reading
├── docs/                    # axioms, specs, ADRs, implementation plans
├── backend/                 # Python modular monolith (Phase 1+)
│   ├── pyproject.toml
│   ├── src/agentic_calendar/
│   └── tests/
├── schemas/                 # generated JSON Schema (committed; cross-language contract)
├── frontend/                # NOT YET — created in Phase 2 alongside the approval UI
└── infra/                   # NOT YET — created when Postgres / Redis are wired up
```

The repo is a **modular monolith** in a **monorepo** with one folder per
language. Phase 1 is backend-only; the frontend and infra folders intentionally
do not exist yet.

## Phase 1 scope

Phase 1 (`docs/implementation-plans/completed/phase-1-core-planning.md`) implements the
deterministic planning core:

- Pydantic contracts for `user_profile`, `motivation_profile`,
  `syllabus_units`, `task_plan`, `validation_result`, and `scheduler_output`.
- A modular validation layer (schema, graph, coverage, user-fit, scheduling
  preconditions) that never mutates inputs.
- A pure greedy Scheduler that emits draft schedules or typed failures with
  debug payloads.
- A deterministic Supervisor with explicit valid and forbidden transitions.
- An immutable plan-version store (the active plan is never mutated in place).
- Deterministic prerequisite logic (`task_plan.prerequisites_met` is forbidden).
- An LLM adapter boundary (`llm_nodes/`) that ships fixture-backed fakes only;
  no real LLM SDK calls in Phase 1.
- Golden test scenarios from `docs/golden-test-cases.md` for every Phase 1
  reason code (3, 4, 5, 6, 10, 11, 12, 15) plus the limited-capacity (1) and
  no-weekday-availability (2) flows.

Phase 1 does **not** include calendar writes, approval UI, drift
classification, RAG ingestion, sponsor reporting, or persistence. The
no-calendar-write invariant is enforced by both the scheduler contract
(`CalendarEventStatus.DRAFT_ONLY` only) and a pytest assertion in every
golden scenario.

## Quickstart

The backend is the only buildable target right now.

```bash
cd backend
uv sync                 # creates backend/.venv from pyproject.toml + uv.lock
uv run pytest           # runs the full Phase 1 test suite
uv run ruff check .     # lint
uv run mypy src         # type check
make schemas            # regenerate /schemas/*.schema.json from Pydantic models
```

See `backend/README.md` for the full developer quickstart.

## Reading order

1. `AGENTS.md`
2. `docs/axioms/00-product-thesis.md`
3. `docs/axioms/01-system-boundaries.md`
4. `docs/axioms/02-state-machine.md`
5. `docs/axioms/04-validation-layer.md`
6. `docs/axioms/05-scheduler-policy.md`
7. `docs/axioms/15-plan-versioning-and-diffs.md`
8. `docs/axioms/16-reliability-patterns.md`
9. `docs/specs/` (canonical schema contracts)
