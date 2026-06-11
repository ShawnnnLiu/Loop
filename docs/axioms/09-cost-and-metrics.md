# 09: Cost and Metrics

## Pricing Assumptions (June 2026)

All estimates assume current pricing as of June 2026 and must be revalidated quarterly:

- **Frontier model** (Strategist; `claude-opus-4-8` in the Phase 8 adapters): $5.00 per 1M input tokens, $25.00 per 1M output tokens.
- **Mid-tier model** (Planner, Reflection, user-facing explanations; `claude-haiku-4-5`): $1.00 per 1M input tokens, $5.00 per 1M output tokens.
- **Embedding**: ~$0.02 per 1M tokens (assumption unchanged; not yet exercised).

If pricing changes by more than 25%, the cost tables below must be regenerated and the change recorded with effective date.

Change log:

- **2026-06-11**: tables regenerated from the April 2026 assumptions ($3.00/$15.00 frontier, $0.15/$0.60 mid-tier) after >25% drift. First live measurement the same day (Phase 8 smoke test, one call per node, small sample inputs): 3,878 input / 2,382 output tokens, $0.0528 estimated — dominated by Strategist output tokens.

## Token Budget per Operation

### Onboarding (one-time per user)

| Operation | Model | Input tokens | Output tokens | Cost |
| --- | --- | --- | --- | --- |
| Strategist (initial syllabus) | Frontier | 8,000 | 4,000 | $0.140 |
| Planner (initial task plan) | Mid-tier | 6,000 | 8,000 | $0.046 |
| RAG retrieval (8 queries) | Embedding | 2,000 | — | $0.00004 |
| **Total onboarding** | | | | **~$0.19** |

### Replan Cycle (drift-triggered, ~weekly per active user)

| Operation | Model | Input tokens | Output tokens | Cost |
| --- | --- | --- | --- | --- |
| Reflection (telemetry → drift summary) | Mid-tier | 2,000 | 500 | $0.0045 |
| Strategist (incremental syllabus update) | Frontier | 6,000 | 3,000 | $0.105 |
| Planner (revised tasks) | Mid-tier | 5,000 | 6,000 | $0.035 |
| **Total per replan** | | | | **~$0.145** |

### Validation Repair Retry

| Operation | Model | Input tokens | Output tokens | Cost |
| --- | --- | --- | --- | --- |
| Planner (re-prompt with violations) | Mid-tier | 6,500 | 6,000 | $0.0365 |

Hard-capped at **2 repair attempts** per cycle. Maximum additional cost: **$0.073**.

### Reflection-Only Cycle (daily batch)

| Operation | Model | Input tokens | Output tokens | Cost |
| --- | --- | --- | --- | --- |
| Reflection per user | Mid-tier | 1,500 | 400 | $0.0035 |

### User-Facing Explanation Generation

| Operation | Model | Input tokens | Output tokens | Cost |
| --- | --- | --- | --- | --- |
| Explanation (per call) | Mid-tier | 1,000 | 300 | $0.0025 |

Approximately 3–5 explanations per active week → **~$0.010 / week**.

## Per-User Monthly LLM Cost Estimate (Active User)

| Component | Frequency | Monthly Cost |
| --- | --- | --- |
| Onboarding (amortized over 6 months) | 1 / 6 mo | $0.031 |
| Replan cycles | ~4 / mo | $0.578 |
| Validation retries | ~3 / mo | $0.110 |
| Reflection batch | ~30 / mo | $0.105 |
| Explanations | ~15 / mo | $0.038 |
| **Total monthly LLM cost** | | **~$0.86** |

## Sensitivity Analysis

If assumptions are off by 2× in either direction:

- **Conservative (high-usage power user)**: ~$1.75 / month.
- **Aggressive (low-usage casual user)**: ~$0.45 / month.

These numbers are order-of-magnitude estimates with explicit assumptions. Real numbers must be measured in production. They must not be used for pricing decisions without validation.

## Total Infrastructure Cost (with all overhead)

| Component | Monthly Range |
| --- | --- |
| LLM | $0.86 – $1.75 |
| Database (Postgres + pgvector) | $0.10 – $0.30 |
| Background workers and queues | $0.05 – $0.15 |
| Calendar API (free at current scale) | $0 |
| Logging, observability, embedding refresh | $0.10 – $0.25 |
| **Total per active user per month** | **$1.10 – $2.45** |

Earlier informal targets ("$1 – $3 per active user per month, ceiling $5 – $10") are superseded by the table above. The range reflects the June 2026 regeneration and the cost controls below.

## At-Scale Estimates (Caveats Apply)

| Active Users | Estimated Monthly Infrastructure |
| --- | --- |
| 1,000 | $1,100 – $2,450 |
| 10,000 | $11,000 – $24,500 |
| 100,000 | Requires renegotiated LLM pricing; likely $50,000 – $120,000 before discounts |

These are order-of-magnitude estimates with explicit assumptions. They are not pricing inputs.

## Plan Pricing (product decision, 2026-06-11)

- **Monthly plan: $39 / month.**
- **Annual plan: $33 / month, billed yearly ($396 / year).**

Against the infrastructure estimate above, serving cost is roughly **3–7% of
revenue** per active user ($1.10 – $2.45 of $33 – $39), with the LLM share at
~2–5%. That headroom is the budget for everything else (support, payment
fees, acquisition) and for the usage estimates being wrong — the sensitivity
band, not the base case, is the planning number.

Plan prices are the recorded product decision; the *cost* figures they are
compared against remain estimates pending production measurement. Re-check
this section whenever the cost tables are regenerated.

## Cost Control Enforcement

- **Per-user hourly cap:** 5 LLM calls per hour.
- **Per-user monthly cap:** $4.00 LLM spend (~5× the expected ~$0.86; alert at 80%). Raised from $2.00 in the 2026-06-11 regeneration to preserve the 5× headroom intent.
- **Per-user retry caps:** 2 validation repair attempts; 2 Scheduler-Planner iterations.
- **Model tiering:** frontier model only for `StrategistNode`; mid-tier for `PlannerNode`, `ReflectionSummaryNode`, and `UserFacingExplanationNode`.
- **Aggressive caching:** identical `user_profile` inputs hit cache for 7 days; see `18-caching-strategy.md`.

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
