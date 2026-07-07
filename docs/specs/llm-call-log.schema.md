# LLM Call Log Schema

## Owner

LLM adapter nodes (`../axioms/22-llm-evaluation-and-observability.md`). Every
real adapter in `llm_nodes/` appends exactly one entry per provider API call.

## Consumers

Eval harness (latency / token / cost aggregates), trace-view operator CLI,
cost-cap monitoring (axiom 09), engineering review.

## Purpose

`LlmCallLog` is the append-only, write-only observability record for every LLM
call made by the five allowed nodes (`StrategistNode`, `PlannerNode`,
`ReflectionSummaryNode`, `UserFacingExplanationNode`, `ResumeIntakeNode`).
Axiom 22 requires that
"every LLM call emits one structured record" carrying tokens, cost, latency,
attempt, validation outcome, and typed `reason_code`.

The log is telemetry, never control plane: no runtime routing decision may read
it (`llm_nodes/` is in the import-linter independence set, so no other region
*can* import it). Eval and trace tooling consume it offline.

## Privacy Rule

The record stores **identifiers, counts, hashes, and outcome metadata only**.
It must **not** contain raw prompts, raw model responses, calendar titles, or
any user-authored text. The contract forbids unknown fields, so a raw-content
field cannot ride along. Raw content capture is a separate, explicit,
retention-limited debug flag on the adapter and is never persisted to this log
(axiom 22 "Per-Call Observability"; mirrors `06-calendar-safety.md`).

## JSON Example

```json
{
  "llm_call_log_id": "llmcall_001",
  "run_id": "run_123",
  "plan_version": "v3",
  "node": "planner",
  "prompt_version": "planner-2026-06-01",
  "model_name": "claude-haiku-4-5-20251001",
  "attempt": 0,
  "sdk_retry": 0,
  "input_tokens": 6100,
  "output_tokens": 7800,
  "cache_creation_tokens": 1024,
  "cache_read_tokens": 4096,
  "cost_estimate_usd": 0.0056,
  "latency_ms": 9400,
  "validation_outcome": "pass",
  "reason_code": null,
  "cache_hit": true,
  "truncated": false,
  "refusal": false,
  "prompt_hash": "a3f1c2d4e5b697881920a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8091a2b3c",
  "response_hash": "b4a2d3e5f6c7a8990a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f6071",
  "created_at": "2026-06-10T14:05:00-07:00"
}
```

## Field Definitions

| Field | Type | Purpose |
| --- | --- | --- |
| `llm_call_log_id` | string | Primary key; unique, used for append-only dedup. |
| `run_id` | string | Deterministic correlation id supplied by the call site. Calls made before any run exists (résumé extraction during onboarding) use a service-minted id with the `intake-` prefix. |
| `plan_version` | string or null | Plan version in play, where applicable; null for calls outside a plan context (e.g. onboarding Strategist). |
| `node` | enum `LlmNodeName`: `strategist`, `planner`, `reflection_summary`, `user_facing_explanation`, `resume_intake` | Which of the five allowed nodes made the call. |
| `prompt_version` | string | Version tag of the prompt template; eval before/after comparisons key on it. |
| `model_name` | string | Provider model id (e.g. `claude-haiku-4-5-20251001`). |
| `attempt` | int ≥ 0 | Validation-repair attempt this call serves: `0` = first generation, `1`–`2` = bounded repair re-prompts (axiom 04 cap). |
| `sdk_retry` | int ≥ 0 | Transport retry index within `attempt`: `0` = first try. Each retry is its own API call and its own log row. |
| `input_tokens` | int ≥ 0 | Provider-reported input token count. With prompt caching enabled this **excludes** cache tokens (the provider reports the tiers separately). |
| `output_tokens` | int ≥ 0 | Provider-reported output token count. |
| `cache_creation_tokens` | int ≥ 0 | The provider's `cache_creation_input_tokens`: input tokens written to the provider prompt cache on this call. Default `0`. |
| `cache_read_tokens` | int ≥ 0 | The provider's `cache_read_input_tokens`: input tokens served from the provider prompt cache on this call. Default `0`. |
| `cost_estimate_usd` | float ≥ 0 | Deterministic estimate from the axiom 09 pricing table, including cache tiers (see below). An **estimate**, not a billing fact. |
| `latency_ms` | int ≥ 0 | Wall-clock call latency. |
| `validation_outcome` | enum: `pass`, `fail` | `pass` iff the call returned output that passed boundary contract re-validation. |
| `reason_code` | enum `ReasonCode` or null | Typed failure code; required when `validation_outcome` is `fail`, null on `pass`. |
| `cache_hit` | boolean | True when the response was served from cache (provider or local) rather than fresh generation. |
| `truncated` | boolean | Provider reported the output was cut off (e.g. max-tokens stop). |
| `refusal` | boolean | Provider refused or returned a safety stop. |
| `prompt_hash` | string (64 hex chars) or null | SHA-256 of the rendered prompt; supports dedup/cache analysis without storing content. |
| `response_hash` | string (64 hex chars) or null | SHA-256 of the raw response text; null when the call produced no response body. |
| `created_at` | datetime | When the call resolved. Timezone-aware. |

Cache-tier accounting (2026-07-05): the adapter uses `cache_control` `ephemeral`
with the 5-minute TTL only. Under that scheme the provider excludes cache
tokens from `usage.input_tokens` and bills `cache_creation_input_tokens` at
**1.25x** and `cache_read_input_tokens` at **0.10x** the base input price —
so `cost_estimate_usd` prices the three input tiers as
`input_tokens * 1.0 + cache_creation_tokens * 1.25 + cache_read_tokens * 0.10`,
all at the input rate, plus output at the output rate. The multipliers are
heuristic pricing constants recorded in `../axioms/09-cost-and-metrics.md`,
not a billing fact.

## Expected Reason Codes On `fail`

The generation codes defined by axiom 22, plus the validation codes the repair
loop already uses:

```text
LLM_CALL_FAILED            # network, timeout, or provider error
LLM_MALFORMED_OUTPUT       # response not parseable into the target shape
LLM_SCHEMA_REJECTED        # parsed but failed boundary contract re-validation
LLM_REFUSAL                # model refused or returned a safety stop
LLM_TRUNCATED              # output cut off (max tokens / incomplete)
LLM_RETRY_LIMIT_EXCEEDED   # SDK-level retries exhausted; fallback engaged
SCHEMA_INVALID             # repair-loop re-validation failure detail
REPAIR_LIMIT_EXCEEDED      # bounded repair attempts exhausted
```

The contract accepts any `ReasonCode` so the audit record can faithfully store
what happened; the list above is what well-behaved adapters emit.

## Required Fields

All fields except `plan_version`, `reason_code`, `prompt_hash`, and
`response_hash` are required. `sdk_retry`, `cache_creation_tokens`,
`cache_read_tokens`, `cache_hit`, `truncated`, and `refusal` default to
`0` / `false`.

## Validation Rules

- `created_at` must be timezone-aware.
- `reason_code` is non-null iff `validation_outcome` is `fail`.
- `refusal` may be true only when `validation_outcome` is `fail` (a refusal
  cannot produce contract-valid output).
- `truncated` is an independent observation: a truncation that still parsed
  and validated stays `pass` (the flag preserves the provider's stop reason).
- `prompt_hash` / `response_hash`, when present, are exactly 64 lowercase hex
  characters.
- Unknown fields are rejected (`extra="forbid"`), which is the structural
  privacy guarantee that raw content cannot be persisted here.

## Invalid Examples

```json
{ "validation_outcome": "pass", "reason_code": "LLM_REFUSAL" }
```

Reason: a passing call must not carry a failure reason code.

```json
{ "validation_outcome": "fail", "reason_code": null }
```

Reason: a failing call must carry a typed reason code.

```json
{ "validation_outcome": "pass", "refusal": true }
```

Reason: a refusal cannot have produced contract-valid output.

```json
{ "prompt_text": "..." }
```

Reason: raw content fields are structurally rejected.

## Append-Only Store Semantics

`InMemoryLlmCallLogStore` (in `llm_nodes/`, mirroring
`accountability/notification_log_store.py`): an `llm_call_log_id` may be
written exactly once; entries are immutable audit facts, never edited. Reads
are `list_for_run(run_id)` (trace view) and `list_all()` (eval aggregates).

## Related Docs

- `../axioms/22-llm-evaluation-and-observability.md`
- `../axioms/09-cost-and-metrics.md`
- `../axioms/04-validation-layer.md`
- `../axioms/16-reliability-patterns.md`
- `../decisions/ADR-0006-llm-never-touches-the-calendar.md`
- `../implementation-plans/phase-8-llm-eval-observability.md`
