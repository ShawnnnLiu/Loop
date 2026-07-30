# Agentic Calendar

Deterministic career-preparation orchestration engine, shipped as the hosted product **Loop** (interview prep, scheduled around your real life).

> **LLMs propose. Deterministic infrastructure disposes.**

LLM nodes generate structured candidates and user-facing explanations.
Deterministic code owns routing, validation, scheduling, approval gates, calendar writes, telemetry, drift classification, and source confidence scoring.
Read `AGENTS.md` and the relevant axioms in `docs/axioms/` before making any substantive change.

## Repository layout

```
Agentic-Calendar/
├── AGENTS.md                # constitution; required reading
├── CLAUDE.md                # operating contract for Claude Code sessions
├── docs/                    # axioms, specs, ADRs, implementation plans, writeups
├── backend/                 # Python modular monolith: deterministic core + FastAPI app
│   ├── src/agentic_calendar/
│   ├── tests/
│   ├── corpus/              # committed grounding-corpus snapshot (BM25 retrieval)
│   ├── taxonomy/            # versioned skill taxonomy + curated groupings
│   ├── pathways/            # generated knowledge maps (make maps)
│   ├── evalsets/            # committed LLM eval recordings (make eval-gate)
│   └── Dockerfile           # production image (serves API + SPA + landing)
├── frontend/                # Loop SPA (React + Vite + TypeScript), thin client of /api
├── landing/                 # static landing, sources, privacy, and terms pages
├── schemas/                 # generated JSON Schema (committed; cross-language contract)
└── fly.toml                 # single-machine Fly.io deploy config (SQLite + WAL)
```

The repo is a **modular monolith** in a **monorepo**.
The backend is the only place control-plane logic lives; the SPA renders state and sends intents.

## What is implemented

The deterministic core:

- Pydantic contracts in `contracts/`, one module per spec in `docs/specs/`, exported to `/schemas`.
- A modular validation layer (schema, graph, coverage, user-fit, scheduling preconditions) with bounded repair and typed `reason_code` failures.
- A pure greedy Scheduler that emits draft-only schedules or typed failures with debug payloads.
- A deterministic Supervisor with explicit valid and forbidden transitions.
- Immutable plan versions (`planning/`) and deterministic prerequisite logic (`prerequisites/`).
- The approval gate and Calendar Write Manager (`approval/`, `calendar_writer/`): the only calendar writer, with `approved_payload_hash` recheck, dry-run, duplicate detection, verification read, and rollback.
- Telemetry and deterministic drift classification (`telemetry/`, `drift/`), plus accountability and disposition tracking.
- Deterministic source-claims scoring and BM25 grounding retrieval (`source_claims/`, `retrieval/`) over the committed corpus snapshot.
- Skill taxonomy, career-track pathways, and generated knowledge maps (`skill_taxonomy/`, `backend/pathways/`).

The propose side and product surface:

- `llm_nodes/` is the only package allowed to import LLM SDKs; it holds the real Anthropic-backed Strategist and Planner adapters plus fixture-backed fakes for tests, gated by committed eval recordings (`make eval-gate`).
- A FastAPI app layer (`app/`) with server-side Google OAuth, session identity, consent, SQLite persistence, and the plan-propose-approve-write loop.
- The Loop SPA in `frontend/` (onboarding, today view, plan generation, schedule review, approval, pathway atlas, accountability dashboard, thresholds).
- Static landing and legal pages in `landing/`, served at `/` by the same server.
- A single-machine hosted deployment on Fly.io behind `loop-study.com` (see `docs/deploy.md`); SQLite + WAL means exactly one machine, no workers.

Import boundaries (LLM SDK isolation, region independence, contracts as leaf) are enforced by `.importlinter`.

## Quickstart

Backend (run from `backend/`):

```bash
cd backend
uv sync --extra dev     # creates backend/.venv from pyproject.toml + uv.lock
make test-fast          # pytest excluding slow golden/boundary/subprocess tests
make check              # lint + typecheck + schema-check + maps-check + full test suite
make schemas            # regenerate /schemas/*.schema.json after intentional contract changes
uv run python -m agentic_calendar.app.web   # keyless dev server on :8000 (fixture LLM nodes, no Google)
```

Frontend (run from `frontend/`, with the dev backend on `:8000`):

```bash
cd frontend
npm install
npm run dev             # http://localhost:5173, proxies /api, /auth, /healthz to :8000
npm run build           # writes frontend/dist/ for the production-like single server
```

See `backend/README.md` and `frontend/README.md` for the full developer quickstarts.

## Reading order

1. `AGENTS.md`
2. `docs/axioms/00-product-thesis.md`
3. `docs/axioms/01-system-boundaries.md`
4. `docs/axioms/02-state-machine.md`
5. `docs/axioms/04-validation-layer.md`
6. `docs/axioms/05-scheduler-policy.md`
7. `docs/axioms/06-calendar-safety.md`
8. `docs/axioms/15-plan-versioning-and-diffs.md`
9. `docs/axioms/16-reliability-patterns.md`
10. `docs/specs/` (canonical schema contracts)

Completed implementation plans live in `docs/implementation-plans/completed/`; active plans stay in `docs/implementation-plans/`.
