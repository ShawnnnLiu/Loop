# 22: LLM Evaluation and Observability

## Principle

The propose side must be measured, not trusted. The deterministic core already earns trust through typed errors, validation gates, and rollback (`16-reliability-patterns.md`). This axiom covers the other half: grading the quality of LLM proposals, enforcing structured generation at the boundary, and observing every model call.

These mechanisms stay strictly inside the propose box. The eval harness grades proposals offline. Observability records calls write-only. Neither may become control-plane state, and neither relaxes any deterministic gate. Drift stays deterministically classified; the eval harness may *grade* the reflection text, but it never lets model output steer the live system.

## Evaluation Is Not Golden Testing

Two different test surfaces, kept separate on purpose:

- **Golden test cases** (`../golden-test-cases.md`) grade the **deterministic system**. They are exact, pass/fail, run on every commit, and never depend on prompt wording.
- **The LLM eval harness** grades **model output quality**. It runs against real or recorded adapters, is allowed to be non-deterministic, and reports **aggregate rates against thresholds** — not per-run pass/fail.

This preserves the existing rule that prompt wording is not a test oracle. The eval set measures whether proposals satisfy the deterministic contracts at a high enough rate; it does not assert that a model emitted a specific string.

Because eval runs are non-deterministic, they MUST NOT gate every commit the way golden tests do. They run on prompt-version or model changes and track trends with alert thresholds.

## Fixed Eval Set

Maintain a curated, versioned eval set that extends the existing fixtures. Each case carries:

- the node input (e.g., a `user_profile` for the Strategist, a `SyllabusUnits` for the Planner);
- the target contract the output must satisfy;
- a deterministic rubric where one exists (e.g., a reflection summary must describe behavior, not identity, per `07-telemetry-and-drift.md`).

The eval set is append-only and versioned so before/after comparisons across prompt changes are meaningful.

## Eval Metrics

Per node, per eval run, tagged with `prompt_version` and `model_name`:

- **Schema-validity rate (pre-repair)** — fraction of raw proposals that satisfy the contract on attempt 0, before any repair.
- **Repair-recovery rate** — fraction of initially-invalid proposals that pass within the bounded 2-attempt repair cap (`04-validation-layer.md`).
- **Post-repair invalid rate** — fraction still invalid after the cap. This is the metric behind the `Invalid Planner output rate <5% after repair` target in `09-cost-and-metrics.md`.
- **Reflection quality** — drift-summary correctness graded against the deterministic rubric: does it match the deterministic `drift_type`, and does it describe behavior rather than diagnose identity. Any LLM-as-judge scoring is advisory only and must be labeled non-authoritative.
- **Latency per node and per plan** and **token cost per plan** — read from observability records, not re-measured.

A prompt change must report before/after on these metrics (for example, "Planner schema-validity 78% → 96% after adding a schema example"). Regressions past threshold block the prompt change, not the build.

## Structured Generation Contract

Real adapters must constrain generation, but the deterministic boundary remains the authority.

- Prefer schema-enforced generation (tool/function calling or constrained JSON) so the model is shaped toward valid output.
- **Never trust the enforcement.** Every node re-validates the parsed output against its Pydantic contract before returning, exactly as the Phase-1 fakes already do (`llm_nodes/base.py`). Schema-enforced decoding reduces failure rate; it does not replace boundary re-validation.
- Generation-side failures are distinct from validation-layer failures and must carry their own typed `reason_code` (below). The deterministic validation repair loop (`04-validation-layer.md`) handles *contract* violations; the generation layer handles *call* failures.

## Generation Reason Codes

```text
LLM_CALL_FAILED            # network, timeout, or provider error
LLM_MALFORMED_OUTPUT       # response not parseable into the target shape
LLM_SCHEMA_REJECTED        # parsed but failed boundary contract re-validation
LLM_REFUSAL                # model refused or returned a safety stop
LLM_TRUNCATED              # output cut off (max tokens / incomplete)
LLM_RETRY_LIMIT_EXCEEDED   # SDK-level retries exhausted; fallback engaged
LLM_AUTH_FAILED            # credentials rejected (401/403) — permanent, never retried
LLM_RATE_LIMITED           # rate limited / overloaded (429/529) — retried with backoff
```

The transport discriminates permanent from transient provider errors: a
permanent rejection (auth, malformed request) fails immediately with its
typed code — retrying it is noise — while transient errors (rate limit,
overload, connection, timeout) retry within the bounded cap with exponential
backoff. Retry caps stay at 2 (axiom 09); backoff changes pacing, not budget.

Each maps to a deterministic next action: transient failures (`LLM_CALL_FAILED`, `LLM_TRUNCATED`) retry within the SDK cap; `LLM_SCHEMA_REJECTED` enters the bounded validation repair loop; exhaustion routes to `error_requires_user`. These are separate from the validation/scheduling `RETRY_LIMIT_EXCEEDED` in `16-reliability-patterns.md`, which counts validation-repair attempts.

## Fallback Behavior

When a node exhausts its SDK-level retries it must fall back deterministically, never silently:

- emit a typed generation `reason_code`;
- record the failure in observability;
- route to the existing error/approval gate rather than fabricating output.

If a node has no safe fallback, it must surface `error_requires_user`, not a guess. No model failure may produce a calendar write.

## Per-Call Observability

Every LLM call emits one structured record. The record is write-only telemetry and never feeds runtime routing.

Required fields:

- `run_id`, `plan_version` where applicable, and the calling node;
- `prompt_version` and `model_name` / model tier;
- `input_tokens`, `output_tokens`, and estimated cost;
- `latency_ms` and `attempt`;
- `validation_outcome` (pass/fail) and the typed `reason_code` on failure;
- `cache_hit` and `truncated` / `refusal` flags;
- timestamp.

Privacy mirrors `06-calendar-safety.md`: do not store raw prompts or raw model responses by default. Store token counts, hashes, and identifiers. Raw content is available only behind an explicit, retention-limited debug flag.

A trace view (an operator CLI, matching the existing `tools/` pattern) renders the LLM calls for a `run_id` in order, with prompt version, tokens, latency, and validation outcome per call. A small trace is enough; it does not need a UI.

## Relationship to the Boundary

This axiom does not widen the LLM's authority. It instruments and grades the four allowed nodes (`StrategistNode`, `PlannerNode`, `ReflectionSummaryNode`, `UserFacingExplanationNode`) and nothing else. See `../decisions/ADR-0006-llm-never-touches-the-calendar.md` for why the boundary sits where it does.

## Test Expectations

- Eval-harness tests assert metric *computation* deterministically (rates from fixed recorded outputs), not live model behavior.
- Generation reason codes have trigger tests for each failure mode using recorded/simulated adapter responses.
- Boundary re-validation tests prove schema-enforced output is still re-validated before return.
- Observability tests assert record completeness and that no raw prompt/response content is persisted without the debug flag.
- A fallback test proves exhaustion routes to `error_requires_user` and never to a calendar write.

## Related Docs

- `01-system-boundaries.md`
- `04-validation-layer.md`
- `07-telemetry-and-drift.md`
- `09-cost-and-metrics.md`
- `16-reliability-patterns.md`
- `../decisions/ADR-0006-llm-never-touches-the-calendar.md`
- `../implementation-plans/phase-8-llm-eval-observability.md`
- `../golden-test-cases.md`
