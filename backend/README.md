# Agentic Calendar — Backend

The deterministic core of the system. Phase 1 implements the planning,
validation, scheduling, supervisor, and plan-versioning packages. Calendar
writes, approvals, persistence, and real LLM adapters land in later phases.

## Setup

```bash
cd backend
uv sync --extra dev
```

This creates `backend/.venv/` and installs runtime + dev dependencies. No
`source .venv/bin/activate` needed; use `uv run <cmd>` (or activate the venv if
you prefer).

## Daily commands

| Command | What it does |
| --- | --- |
| `make test` | Full pytest suite |
| `make test-fast` | Pytest excluding `@pytest.mark.golden` |
| `make lint` | `ruff check .` |
| `make typecheck` | `mypy --strict` over `src/` |
| `make boundaries` | `import-linter` — fails CI if a region imports a sibling |
| `make schemas` | Regenerate `/schemas/*.schema.json` from Pydantic |
| `make check` | lint + typecheck + boundaries + test |
| `make format` | `ruff format` (writes changes) |

## Module layout (Phase 1)

```
src/agentic_calendar/
├── common/         # tiny shared kernel (clock, ids, errors, logging)
├── contracts/      # Pydantic models, one module per spec in docs/specs/
├── supervisor/     # pure routing function + state enum + transition table
├── prerequisites/  # deterministic prerequisite computation (axiom 11)
├── validation/     # five-category validation layer (axiom 04)
├── scheduler/      # pure greedy MVP scheduler (axiom 05)
├── planning/       # immutable plan versions + generation history (axiom 15)
├── llm_nodes/      # the ONLY package allowed to import LLM SDKs (axiom 01)
└── tools/          # operator CLIs (e.g. export_schemas)
```

Architectural rules are enforced by `.importlinter`:

1. **LLM SDK isolation** — only `llm_nodes/` and `tools/` may import
   `openai`/`anthropic`/etc.
2. **Region independence** — `supervisor`, `validation`, `scheduler`, etc.
   must not import each other; cross-region contracts go through
   `contracts/`.
3. **Contracts is leaf** — `contracts/` may only depend on `common/`.

If you find yourself wanting to break one of these rules, that is a design
signal — read the relevant axiom before adding a workaround.

## Test layout

Mirrors `src/` one-to-one:

```
tests/
├── conftest.py       # FrozenClock, deterministic ID seeding, fixture loader
├── contracts/        # one test file per Pydantic contract
├── supervisor/
├── prerequisites/
├── validation/
├── scheduler/
├── planning/
├── llm_nodes/
├── tools/
├── boundaries/       # import-linter contracts run as pytest tests
├── golden/           # docs/golden-test-cases.md scenarios (Phase 1 subset)
└── fixtures/
    ├── valid/<contract>/*.json
    └── invalid/<contract>/*.json + *.expected.json
```

Each invalid fixture has a paired `.expected.json` describing the expected
typed `reason_code` and structured violations. Tests assert against those
expectations rather than against prompt wording, per `040-testing-and-invariants.mdc`.

## Phase 1 implementation notes

- **Capacity-promotion in the scheduler.** When the total required minutes
  across placeable tasks exceeds available capacity, per-task
  `NO_VALID_CONTIGUOUS_BLOCK` failures are promoted to
  `INSUFFICIENT_WEEKLY_CAPACITY` with the `extend_timeline` repair hint
  (axiom 05). Fragmentation failures (capacity sufficient, no contiguous
  block) keep their original code with a `split_task` hint.
- **No calendar writes.** Phase 1 deliberately stops at
  `AWAITING_USER_APPROVAL`. The scheduler contract enforces
  `CalendarEventStatus.DRAFT_ONLY` and every golden scenario asserts that no
  `calendar_event_id` leaks out of the planning core (axiom 06).
- **LLM nodes are fakes.** `llm_nodes/` ships fixture-backed
  `FixtureStrategist`, `FixturePlanner`, a deterministic
  `DeterministicUserFacingExplanation`, and a `StubReflectionSummary` that
  raises `NotImplementedError` until Phase 4. The `import-linter`
  contract makes sure the real SDK can only ever be added under
  `llm_nodes/` or `tools/`.
