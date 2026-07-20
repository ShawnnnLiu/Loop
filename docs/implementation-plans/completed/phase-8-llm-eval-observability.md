# Phase 8: LLM Evaluation, Structured Generation, and Observability

Status: **complete** — implemented and merged to `main`.

## Goal

Make the propose side measurable and reliable. Build an evaluation harness that grades LLM proposal quality, enforce structured generation at the boundary with deterministic fallback, and record per-call observability — without granting the LLM any new authority.

## Position in the Roadmap

Phases 1–3 shipped the deterministic core. The four `llm_nodes/` are still fixture-backed fakes (`FixturePlanner`, `FixtureStrategist`, the reflection/explanation stubs), and `llm_nodes/base.py` defers all real-model behavior to "real adapters." Phase 8 is the cross-cutting LLM-reliability layer that **activates when those fakes are replaced by real SDK adapters**. It can begin as soon as the first real adapter lands; it does not depend on Phases 4–7, and Phases 4–7 do not depend on it (drift, RAG confidence, and accountability are all deterministic and run fine on fakes).

This phase reinforces the propose/dispose boundary. It instruments and grades the four allowed nodes and nothing else. Dispose stays deterministic.

## Required Docs

- `../../../AGENTS.md`
- `../../axioms/01-system-boundaries.md`
- `../../axioms/04-validation-layer.md`
- `../../axioms/09-cost-and-metrics.md`
- `../../axioms/16-reliability-patterns.md`
- `../../axioms/22-llm-evaluation-and-observability.md`
- `../../decisions/ADR-0006-llm-never-touches-the-calendar.md`
- `../../golden-test-cases.md`

## Deliverables

### 1. Eval Harness (do this first)

- A fixed, versioned eval set extending the existing fixtures, with input + target contract + deterministic rubric per case.
- Metric computation for: schema-validity rate (pre-repair), repair-recovery rate, post-repair invalid rate, reflection quality vs. rubric, latency per node/plan, token cost per plan.
- Runs tagged with `prompt_version` and `model_name`; results stored so before/after comparisons across prompt changes are reproducible.
- A runner that executes against real or recorded adapters and reports rates against thresholds (not per-run pass/fail).

### 2. Structured Generation and Fallback

- Real SDK adapters for the four nodes using schema-enforced generation (tool/function calling or constrained JSON).
- Boundary re-validation retained: parsed output is re-validated against the Pydantic contract before return, regardless of enforcement.
- Generation reason codes wired through: `LLM_CALL_FAILED`, `LLM_MALFORMED_OUTPUT`, `LLM_SCHEMA_REJECTED`, `LLM_REFUSAL`, `LLM_TRUNCATED`, `LLM_RETRY_LIMIT_EXCEEDED`.
- Deterministic fallback: bounded SDK retries, then route to the existing error/approval gate. No silent failure; no fabricated output.

### 3. Per-Call Observability

- A `llm_call_log` record emitted per call (see new spec below): `run_id`, node, `prompt_version`, `model_name`/tier, input/output tokens, cost estimate, `latency_ms`, `attempt`, `validation_outcome` + `reason_code`, `cache_hit`, `truncated`/`refusal` flags, timestamp.
- Privacy: no raw prompt/response persisted by default; token counts, hashes, and IDs only; raw content behind a retention-limited debug flag.
- A trace-view operator CLI (matching the `tools/` pattern, e.g. alongside `visualize.py`) that renders all LLM calls for a `run_id`.

### 4. Spec and Docs

- New spec: `../../specs/llm-call-log.schema.md` for the observability record.
- The structured-generation and fallback decisions documented in `22-llm-evaluation-and-observability.md` (axiom) and ADR-0006 (boundary rationale) — both authored as part of this work.

## Acceptance Criteria

- Eval metrics are computed deterministically from recorded outputs; the harness reports rates, not exact strings.
- A prompt change produces a before/after report on schema-validity and repair-recovery rates.
- Schema-enforced output is still re-validated at the boundary before any consumer uses it.
- Every generation failure carries a typed `reason_code` and is recorded in observability.
- Retry exhaustion routes to `error_requires_user`; no model failure can produce a calendar write.
- No raw prompt or response content is persisted without the explicit debug flag.
- The `post-repair invalid rate` metric is measurable against the `<5%` target in `09-cost-and-metrics.md`.

## Explicit Non-Goals

- LLM-controlled routing, scheduling, approvals, or calendar writes (forbidden by `01-system-boundaries.md`).
- LLM-based drift classification (stays deterministic per `07-telemetry-and-drift.md`).
- Eval results feeding runtime routing decisions — evals are offline; observability is write-only.
- A full hosted observability product or dashboard UI — a trace CLI is sufficient for the MVP.
- Per-commit gating on non-deterministic eval runs — those run on prompt/model changes only.
- Autonomous prompt tuning.

## Test Expectations

- Metric-computation tests over fixed recorded outputs (deterministic).
- Trigger test for each generation reason code using recorded/simulated adapter responses.
- Boundary re-validation test: enforced output is still rejected when it violates the contract.
- Fallback test: SDK-retry exhaustion routes to `error_requires_user`, never a write.
- Observability tests: record completeness; no raw content persisted without the debug flag.
- Privacy test: trace output contains no raw calendar titles, prompts, or responses by default.
