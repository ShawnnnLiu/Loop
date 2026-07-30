# Agentic Calendar - Backend

The Python modular monolith behind Loop: the deterministic core (contracts, validation, scheduling, supervisor, plan versioning, approval gate, calendar writes) plus the FastAPI app layer and the Anthropic-backed LLM adapters.
Deterministic code owns all control-plane state; `llm_nodes/` is the only package allowed to import LLM SDKs.

## Setup

```bash
cd backend
uv sync --extra dev
```

This creates `backend/.venv/` and installs runtime + dev dependencies.
No `source .venv/bin/activate` needed; use `uv run <cmd>` (or activate the venv if you prefer).

## Daily commands

| Command | What it does |
| --- | --- |
| `make test` | Full pytest suite |
| `make test-fast` | Pytest excluding slow tests (`golden`, `boundary`, `subprocess` markers) |
| `make lint` | `ruff check .` |
| `make typecheck` | `mypy --strict` over `src/` |
| `make boundaries` | `import-linter` contracts (also run inside `make test`) |
| `make schemas` | Regenerate `/schemas/*.schema.json` from Pydantic contracts |
| `make schema-check` | Verify committed `/schemas` match the contracts (no write) |
| `make maps` | Regenerate `pathways/knowledge_maps.json` from the curated grouping |
| `make maps-check` | Verify the committed knowledge maps match a fresh regeneration |
| `make eval-gate` | Strict-grade committed LLM eval recordings in `evalsets/` (offline) |
| `make retrieval-eval` | Grade the labeled retrieval query set against `corpus/corpus.db` |
| `make check` | lint + typecheck + schema-check + maps-check + test |
| `make format` | `ruff format` (writes changes) |

Run the keyless dev server (fixture LLM nodes, no Anthropic key, no Google; auto-onboards a sample profile):

```bash
uv run python -m agentic_calendar.app.web   # http://127.0.0.1:8000
```

## Module layout

```
src/agentic_calendar/
├── common/              # tiny shared kernel (clock, ids, errors, logging)
├── contracts/           # Pydantic models, one module per spec in docs/specs/
├── supervisor/          # pure routing function + state enum + transition table
├── prerequisites/       # deterministic prerequisite computation (axiom 11)
├── validation/          # five-category validation layer (axiom 04)
├── scheduler/           # pure greedy draft-only scheduler (axiom 05)
├── planning/            # immutable plan versions + generation history (axiom 15)
├── approval/            # approval-event persistence; the gate before any write (axiom 06)
├── calendar_writer/     # Calendar Write Manager, the ONLY external-calendar writer (axiom 06)
├── telemetry/           # privacy-first capture of how scheduled tasks executed (axiom 07)
├── drift/               # deterministic rule-based drift classifier (axiom 07)
├── accountability/      # sponsor-reporting slice of the accountability layer
├── disposition/         # append-only completion / skip / drop memory
├── duration_estimation/ # deterministic estimation kernel (axiom 17)
├── source_claims/       # deterministic claim ingestion + confidence scoring (axiom 08)
├── retrieval/           # corpus registry, chunking, BM25 grounding retrieval (axiom 08)
├── skill_taxonomy/      # checked-in skill vocabulary + career-track taxonomy
├── narrative/           # deterministic pathway fit, gaps, and story progress
├── overlay/             # append-only knowledge-map overlay store
├── cache/               # deterministic byte-stable cache keys (axiom 18)
├── templates/           # curated, review-gated literal registries
├── consent/             # deterministic opt-in surface for cross-user data use
├── identity/            # per-user Google identity + credential persistence
├── llm_nodes/           # the ONLY package allowed to import LLM SDKs (axiom 01)
├── app/                 # composition root: FastAPI server, OAuth, SQLite persistence
└── tools/               # operator CLIs (calendar ops, corpus ops, evals, schema export)
```

Sibling data directories: `corpus/` (committed grounding-corpus snapshot), `taxonomy/` (versioned skill taxonomy + curated groupings), `pathways/` (generated knowledge maps), `evalsets/` (committed LLM eval recordings), and `Dockerfile` (the production image; see the repo-root `fly.toml`).

Architectural rules are enforced by `.importlinter` (21 contracts):

1. **LLM SDK isolation** - only `llm_nodes/` and `tools/` may import LLM SDKs.
2. **Region independence** - region packages must not import each other; cross-region data goes through `contracts/`.
3. **Per-region allowlists** - leaf kernels (`prerequisites/`, `approval/`, `telemetry/`, `retrieval/`, ...) each have an explicit dependency allowlist, usually `common/` + `contracts/` only.
4. **Contracts is leaf** - `contracts/` may only depend on `common/`.

`app/` and `tools/` sit outside the region set and may compose any region.
If you find yourself wanting to break one of these rules, that is a design signal - read the relevant axiom before adding a workaround.

## Test layout

Mirrors `src/` one-to-one (one test package per region, plus `web/` for the app layer), with these extras:

```
tests/
├── conftest.py       # FrozenClock, deterministic ID seeding, fixture loader
├── boundaries/       # import-linter contracts run as pytest tests
├── golden/           # docs/golden-test-cases.md scenarios
└── fixtures/
    ├── valid/<contract>/*.json
    └── invalid/<contract>/*.json + *.expected.json
```

Each invalid fixture has a paired `.expected.json` describing the expected typed `reason_code` and structured violations.
Tests assert against those expectations rather than against prompt wording, per `040-testing-and-invariants.mdc`.

## LLM adapters and evals

`llm_nodes/` ships both the real Anthropic-backed adapters (Strategist, Planner) used by the hosted app and fixture-backed fakes used everywhere in the test suite.
The deterministic test suite never calls an LLM.
Adapter behavior is instead gated offline: `make eval-gate` strict-grades the committed recordings in `evalsets/`, and `make retrieval-eval` grades the labeled query set against the pinned corpus snapshot.

## Calendar safety

The scheduler emits draft-only output (`CalendarEventStatus.DRAFT_ONLY`).
`calendar_writer/` is the only package that writes to external calendars, and no write is valid without `approval_event_id`, `run_id`, `task_id`, `plan_version`, an `approved_payload_hash` recheck against the live draft, and a calendar target identifier.
Every write path supports dry-run, duplicate detection by metadata, verification read after write, and rollback via the stored `calendar_event_mapping`.
