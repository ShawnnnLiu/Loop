# 09: Cost and Metrics

## Pricing Assumptions (September 2026)

All estimates assume current pricing as of September 2026 and must be revalidated quarterly:

- **Frontier model** (Strategist; `claude-opus-5-5` since 2026-09-23, effort `low`, previously `claude-opus-4-8` with thinking off): $4.00 per 1M input tokens, $20.00 per 1M output tokens; cache reads at 0.05x base input on this model (0.10x elsewhere). Thinking cannot be disabled on this model, so its thinking tokens bill as output inside the node's 16k cap.
- **Sonnet-tier model** (Planner, Reflection, user-facing explanations, eval judge; `claude-sonnet-5`): $2.00 per 1M input tokens, $10.00 per 1M output tokens. The launch $2.00/$10.00 was announced as introductory through 2026-08-31 with a rise to $3.00/$15.00 on 2026-09-01; the provider cancelled that rise and made $2.00/$10.00 the standard price, so the adapters were re-pinned from the sticker they had encoded (2026-09-23).
- **Haiku-tier model** (ResumeIntake; `claude-haiku-4-5`): $1.00 per 1M input tokens, $5.00 per 1M output tokens (same figures as the pre-2026-07-04 mid-tier entry in the change log).
- **Embedding** (retrieval grounding, Voyage `voyage-3.5`): $0.06 per 1M tokens — first exercised 2026-07-06 (grounding G-E). Offline corpus embedding only (chunks + labeled queries, cached by content hash — embed once per text per model); embeddings are not in any runtime request path yet, so per-user cost tables are unaffected until retrieval-time query embedding ships.

Prompt-cache tiers (2026-07-05): with the adapter's 5-minute-TTL `ephemeral`
caching, the provider excludes cache tokens from `input_tokens` and bills cache
**writes at 1.25x** and cache **reads at 0.10x** the base input price (0.05x on
`claude-opus-5-5`; the multiplier is now a per-config constant). Per-call
`cost_estimate_usd` on `llm_call_log` rows now includes both tiers (2026-07-05
audit fix); the multipliers are heuristic pricing constants pending production
measurement, like every figure here. The budget tables below predate caching
and are deliberately not rewritten — they remain cache-free upper-bound-style
estimates.

Token-count caveat: `claude-sonnet-5` uses a newer tokenizer that counts roughly 30% more tokens for the same text than the Haiku-era counts the budgets below were originally written against. The budgets are heuristic priors either way; recalibrate them from live call-log measurements, not by applying a blanket multiplier.

If pricing changes by more than 25%, the cost tables below must be regenerated and the change recorded with effective date.

Change log:

- **2026-09-23**: Strategist moved from `claude-opus-4-8` ($5.00/$25.00,
  thinking off) to `claude-opus-5-5` ($4.00/$20.00, effort `low`; the model
  rejects thinking-off, so effort is its only thinking control and the
  adapter gained a per-node `effort` knob). Decided by an offline-graded
  live comparison on the same day, same v8 prompt bytes (recordings
  `opus48_*` / `opus55_low_*`, reports alongside). Headline numbers are
  from the 40-case grounded set `eval_set_v10` (derived from the pinned
  corpus by `build_grounded_eval_set`; built because the 3-case v4 set
  swung coverage 0.64 → 0.23 on the SAME model between July and
  September): schema validity 1.0 → 1.0; citation coverage 0.2907 → 0.2631
  (a wash inside run-to-run noise); claim utilization 0.4717 → 0.5917;
  advisory groundedness judge mean 3.62 → 4.33; strategist cost over the 40
  cases $2.37 → $1.95 (-18%, thinking tokens included); latency p50 14.9 s
  → 11.2 s, p95 18.3 s → 13.3 s. The effort sweep the migration guide asks
  for was run on the same set: opus-5-5 at `medium` reaches coverage 0.2747
  / utilization 0.6650 / judge 4.38 but costs $2.62 over the 40 cases
  (more than opus-4-8) at p50 18.2 s — `low` is the shipped level. The
  small v2/v4 pairs pointed the same
  way on cost and validity but overstated the grounding gain (v4 coverage
  0.2254 → 0.4190 on three cases) — the reason the 40-case set exists.
  Coverage is low on BOTH arms for `swe` profiles (~0.05–0.07): the
  corpus's SWE claims are generic blog excerpts the syllabus rarely cites —
  a claim-curation signal, not a model signal. Sonnet tier
  re-pinned $3.00/$15.00 → $2.00/$10.00 (the provider made the launch price
  standard instead of raising it on 2026-09-01). The Sonnet drop exceeds
  the 25% rule, so every table below was regenerated the same day at
  $4.00/$20.00 frontier, $2.00/$10.00 Sonnet-tier, $1.00/$5.00 Haiku-tier
  with the token budgets unchanged: onboarding ~$0.28 → ~$0.20, replan
  ~$0.22 → ~$0.16, monthly LLM ~$1.70 → ~$1.19, infrastructure
  $1.95–$4.10 → $1.44–$3.08. The monthly cap stays $8.00 (now ~6.7× the
  expected spend rather than ~5×; lowering a control is a separate
  decision). The additive story-layer and résumé rows moved only where
  their tier's price moved.
- **2026-07-20**: story-layer explanation targets (narrative pathways, NP-F)
  implemented and first exercised. The pathway fit note and story summary are
  two prompt targets inside `UserFacingExplanationNode`, both on the Haiku tier
  (`claude-haiku-4-5`, $1.00/$5.00) — a deliberate per-target divergence from
  that node's Sonnet-tier validation-explanation target (see the model-tiering
  line below). They match the NP-A "Story Layer" budget row (~$0.005 each);
  no figure moved, tables not regenerated.
- **2026-07-19**: story-layer (narrative pathways, NP-A) budget lines added.
  Evidence tagging rides the existing résumé-extraction call (+~300-600 input, +~200 output tokens on the Haiku tier; extraction stays ~$0.01, user-initiated).
  Pathway fit notes are one batched Haiku-tier call per Your-story visit (~$0.005); story summaries are user-initiated Haiku-tier calls (~$0.005).
  No background LLM calls anywhere in the feature.
  Tables NOT regenerated - the "Story Layer" table below is additive and no existing figure moved.
- **2026-07-06**: embedding line exercised for the first time (grounding
  G-E): provider decision recorded as Voyage `voyage-3.5` at $0.06 per 1M
  tokens, replacing the dormant ~$0.02 assumption (a >25% change, but
  embedding cost appears in no runtime budget table — only the onboarding
  "RAG retrieval" line item, updated below). One-time corpus embed
  (564 chunks + 57 labeled queries, snapshot `snap_b0ce947cafdafc8b`) costs
  ~$0.013; the vector cache makes re-runs free until the corpus or model
  changes. Per-refresh cost measured at the G-I six-track expansion:
  growing the corpus 35 → 55 documents embedded only the 242 new chunks +
  18 new queries (82,616 tokens, ~$0.005) — the content-hash cache makes
  refresh cost proportional to what changed, not to corpus size.
- **2026-07-06**: `ResumeIntakeNode` added on the Haiku tier
  (`claude-haiku-4-5`, $1.00/$5.00). The onboarding table gains an additive
  résumé-extraction row; tables NOT regenerated — the row is additive and no
  existing figure moved.
- **2026-07-05**: cache-tier pricing added to per-call cost estimation
  (`AdapterConfig.estimate_cost_usd` / `llm_call_log.cost_estimate_usd`):
  cache writes at 1.25x and cache reads at 0.10x the input rate (5-minute
  TTL). The previous input-only formula systematically understated spend on
  cached calls after the A2 prompt-caching change. Cost tables unchanged
  (bs-detector audit fix).
- **2026-07-04**: Planner, Reflection, and Explanation upgraded from `claude-haiku-4-5` ($1.00/$5.00) to `claude-sonnet-5` ($3.00/$15.00) for user-facing quality (UX quality pass D3; Strategist stays frontier). Mid-tier prices tripled, so all tables regenerated. Monthly cap raised $4.00 → $8.00 to preserve the ~5× headroom intent.
- **2026-06-11**: tables regenerated from the April 2026 assumptions ($3.00/$15.00 frontier, $0.15/$0.60 mid-tier) after >25% drift. First live measurement the same day (Phase 8 smoke test, one call per node, small sample inputs): 3,878 input / 2,382 output tokens, $0.0528 estimated — dominated by Strategist output tokens.

## Token Budget per Operation

### Onboarding (one-time per user)

| Operation | Model | Input tokens | Output tokens | Cost |
| --- | --- | --- | --- | --- |
| Strategist (initial syllabus) | Frontier | 8,000 | 4,000 | $0.112 |
| Planner (initial task plan) | Sonnet-tier | 6,000 | 8,000 | $0.092 |
| RAG retrieval (8 queries) | Embedding | 2,000 | — | $0.00012 |
| Résumé extraction | Haiku-tier (`claude-haiku-4-5`) | 3,500 | 800 | $0.008 |
| **Total onboarding** | | | | **~$0.20** |

Résumé extraction is user-initiated (the Extract button; 0 or more presses
per onboarding) and a heuristic prior like every figure here; it is excluded
from the one-time total above, which predates it and was deliberately not
regenerated.

### Replan Cycle (drift-triggered, ~weekly per active user)

| Operation | Model | Input tokens | Output tokens | Cost |
| --- | --- | --- | --- | --- |
| Reflection (telemetry → drift summary) | Sonnet-tier | 2,000 | 500 | $0.009 |
| Strategist (incremental syllabus update) | Frontier | 6,000 | 3,000 | $0.084 |
| Planner (revised tasks) | Sonnet-tier | 5,000 | 6,000 | $0.070 |
| **Total per replan** | | | | **~$0.16** |

### Validation Repair Retry

| Operation | Model | Input tokens | Output tokens | Cost |
| --- | --- | --- | --- | --- |
| Planner (re-prompt with violations) | Sonnet-tier | 6,500 | 6,000 | $0.073 |

Hard-capped at **2 repair attempts** per cycle. Maximum additional cost: **$0.146**.

### Reflection-Only Cycle (daily batch)

| Operation | Model | Input tokens | Output tokens | Cost |
| --- | --- | --- | --- | --- |
| Reflection per user | Sonnet-tier | 1,500 | 400 | $0.007 |

### User-Facing Explanation Generation

| Operation | Model | Input tokens | Output tokens | Cost |
| --- | --- | --- | --- | --- |
| Explanation (per call) | Sonnet-tier | 1,000 | 300 | $0.005 |

Approximately 3–5 explanations per active week → **~$0.020 / week**.

### Story Layer (Narrative Pathways)

| Operation | Model | Input tokens | Output tokens | Cost |
| --- | --- | --- | --- | --- |
| Evidence tagging (rides the résumé-extraction call) | Haiku-tier | +500 | +200 | +$0.002 |
| Pathway fit notes (one batched call per Your-story visit) | Haiku-tier | 1,500 | 400 | $0.005 |
| Story summary (user-initiated refresh) | Haiku-tier | 1,500 | 400 | $0.005 |

Every story-layer call is user-initiated; the feature makes no background LLM calls.
Fit, gaps, and slot states are computed deterministically at zero LLM cost (axiom 00).
These are heuristic priors like every figure here; they are excluded from the monthly totals above, which predate the story layer and were deliberately not regenerated.

## Per-User Monthly LLM Cost Estimate (Active User)

| Component | Frequency | Monthly Cost |
| --- | --- | --- |
| Onboarding (amortized over 6 months) | 1 / 6 mo | $0.034 |
| Replan cycles | ~4 / mo | $0.652 |
| Validation retries | ~3 / mo | $0.219 |
| Reflection batch | ~30 / mo | $0.210 |
| Explanations | ~15 / mo | $0.075 |
| **Total monthly LLM cost** | | **~$1.19** |

## Sensitivity Analysis

If assumptions are off by 2× in either direction:

- **Conservative (high-usage power user)**: ~$2.38 / month.
- **Aggressive (low-usage casual user)**: ~$0.60 / month.

These numbers are order-of-magnitude estimates with explicit assumptions. Real numbers must be measured in production. They must not be used for pricing decisions without validation.

## Total Infrastructure Cost (with all overhead)

| Component | Monthly Range |
| --- | --- |
| LLM | $1.19 – $2.38 |
| Database (Postgres + pgvector) | $0.10 – $0.30 |
| Background workers and queues | $0.05 – $0.15 |
| Calendar API (free at current scale) | $0 |
| Logging, observability, embedding refresh | $0.10 – $0.25 |
| **Total per active user per month** | **$1.44 – $3.08** |

Earlier informal targets ("$1 – $3 per active user per month, ceiling $5 – $10") are superseded by the table above. The range reflects the September 2026 regeneration (Opus 5.5 Strategist, Sonnet 5 standard pricing) and the cost controls below.

## At-Scale Estimates (Caveats Apply)

| Active Users | Estimated Monthly Infrastructure |
| --- | --- |
| 1,000 | $1,440 – $3,080 |
| 10,000 | $14,400 – $30,800 |
| 100,000 | Requires renegotiated LLM pricing; likely $70,000 – $150,000 before discounts |

These are order-of-magnitude estimates with explicit assumptions. They are not pricing inputs.

## Plan Pricing (product decision, 2026-06-11)

- **Monthly plan: $39 / month.**
- **Annual plan: $33 / month, billed yearly ($396 / year).**

Against the infrastructure estimate above, serving cost is roughly **4–9% of
revenue** per active user ($1.44 – $3.08 of $33 – $39), with the LLM share at
~3–7%. That headroom is the budget for everything else (support, payment
fees, acquisition) and for the usage estimates being wrong — the sensitivity
band, not the base case, is the planning number. Re-checked 2026-07-04 after
the Sonnet-tier upgrade and again 2026-09-23 after the Opus 5.5 / Sonnet 5
price drops: margins widen; no pricing change required.

Plan prices are the recorded product decision; the *cost* figures they are
compared against remain estimates pending production measurement. Re-check
this section whenever the cost tables are regenerated.

## Cost Control Enforcement

- **Per-user hourly cap:** 5 LLM calls per hour. Call-count-based, so unaffected by the pricing change; re-checked 2026-07-04 and kept.
- **Per-user monthly cap:** $8.00 LLM spend (~6.7× the expected ~$1.19; alert at 80%). Raised from $4.00 in the 2026-07-04 regeneration (and from $2.00 in the 2026-06-11 one) to preserve the 5× headroom intent; kept at the 2026-09-23 regeneration rather than lowered — a control change is a separate decision.
- **Per-user retry caps:** 2 validation repair attempts; 2 Scheduler-Planner iterations.
- **Model tiering:** frontier model only for `StrategistNode`; Sonnet-tier for `PlannerNode`, `ReflectionSummaryNode`, and `UserFacingExplanationNode`'s validation-explanation target (upgraded from small-tier 2026-07-04 — these nodes write every task title and user-facing sentence, so perceived quality lives here); Haiku-tier for `ResumeIntakeNode` and, since NP-F, `UserFacingExplanationNode`'s two story-layer targets (pathway fit note + story summary) — short decorative prose derived from already-confirmed structured state (kernel coverage), user-initiated, held to a deterministic post-check; the cheapest tier is sufficient.
- **Aggressive caching:** identical `user_profile` inputs hit cache for 7 days; see `18-caching-strategy.md`. (Status: realized but unwired — no production composition root constructs the object cache; see 18's wiring-status note. Not an active enforcement mechanism.)

## Scheduling Quality Metrics

- Generated schedules require **<25%** manual task edits.
- Calendar duplicate event rate = **0**.
- Calendar write rollback success rate = **100%**.
- Median scheduling latency stays below product threshold.
- Approval rate of first-draft schedules **>70%** (Phase 2 target).
- Unscheduled task rate per planning cycle **<10%**.

If approval rate sustains below **60%** or manual edit rate sustains above **30%** for 4 weeks, the Scheduler is the bottleneck. See `05-scheduler-policy.md` for the upgrade path.

## Task Quality Metrics

- Median duration estimate error **<30%**.
- High-priority module coverage = **100%**.
- Invalid Planner output rate **<5%** after repair.
- Task dependency graph validity = **100%**.

## User Behavior Metrics

- Users complete **>60%** of scheduled tasks over 2 weeks.
- Weekly active retention improves over baseline.
- Replan frequency remains manageable.
- User override rate decreases over time.
- Approval rate of generated schedules increases over time.

## Accountability Quality Metrics

- Users with accountability enabled complete more scheduled work than users with accountability disabled.
- Weekly check-in completion rate is **>60%**.
- Recovery-plan acceptance rate is **>40%**.
- Users who trigger recovery mode show improved completion in the following week.
- Private nudges reduce missed tasks without increasing churn.
- Sponsor reports are opened by sponsors at a meaningful rate.
- Sponsor-enabled users do not churn at a higher rate than non-sponsor users (i.e., no "perceived surveillance" churn).

## Privacy and Trust Quality Metrics

- Unauthorized sponsor report rate = **0**.
- Sponsor visibility violation rate = **0**.
- Raw calendar title exposure rate = **0**.
- User complaint rate about parent or sponsor overexposure stays below the product threshold.
- Users can disable sponsor reporting without breaking the active plan.

## Drift Quality Metrics

- Drift classification precision improves after manual review.
- Missed tasks decrease after drift intervention.
- Duration prediction error decreases after calibration.
- Accountability interventions reduce low-engagement drift over time.

## Operational Metrics

- Validation failure rate by `reason_code`.
- Scheduler failure rate by `reason_code`.
- Calendar verification failure rate.
- Rollback success rate.
- LLM retry count per successful plan.
- Approval-hash mismatch rate (target: 0; mismatches are P1 incidents per `06-calendar-safety.md`).
- Offline completion sync queue depth and reconciliation rate (per `19-always-online-mvp.md`).

## Disclosure

The token budgets and cost ranges in this document are computed from current pricing and assumed usage. Internal documentation must label them as estimates pending production validation. Do not present them as measured costs in customer commitments or financial models without production data. The plan prices in "Plan Pricing" are the recorded product decision and may be stated externally; the margin math comparing them to estimated costs may not.

## Related Docs

- `05-scheduler-policy.md`
- `07-telemetry-and-drift.md`
- `08-rag-source-claims.md`
- `17-duration-estimation.md`
- `18-caching-strategy.md`
- `19-always-online-mvp.md`
- `21-accountability-layer.md`
- `22-llm-evaluation-and-observability.md`
- `../decisions/ADR-0004-no-per-user-ml-model-in-mvp.md`
