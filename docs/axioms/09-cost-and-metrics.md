# 09: Cost and Metrics

## Pricing Assumptions (April 2026)

All estimates assume current pricing as of April 2026 and must be revalidated quarterly:

- **Frontier model** (Strategist): ~$3.00 per 1M input tokens, ~$15.00 per 1M output tokens.
- **Mid-tier model** (Planner, Reflection, user-facing explanations): ~$0.15 per 1M input tokens, ~$0.60 per 1M output tokens.
- **Embedding**: ~$0.02 per 1M tokens.

If pricing changes by more than 25%, the cost tables below must be regenerated and the change recorded with effective date.

## Token Budget per Operation

### Onboarding (one-time per user)

| Operation | Model | Input tokens | Output tokens | Cost |
| --- | --- | --- | --- | --- |
| Strategist (initial syllabus) | Frontier | 8,000 | 4,000 | $0.084 |
| Planner (initial task plan) | Mid-tier | 6,000 | 8,000 | $0.0057 |
| RAG retrieval (8 queries) | Embedding | 2,000 | — | $0.00004 |
| **Total onboarding** | | | | **~$0.090** |

### Replan Cycle (drift-triggered, ~weekly per active user)

| Operation | Model | Input tokens | Output tokens | Cost |
| --- | --- | --- | --- | --- |
| Reflection (telemetry → drift summary) | Mid-tier | 2,000 | 500 | $0.0006 |
| Strategist (incremental syllabus update) | Frontier | 6,000 | 3,000 | $0.063 |
| Planner (revised tasks) | Mid-tier | 5,000 | 6,000 | $0.0044 |
| **Total per replan** | | | | **~$0.068** |

### Validation Repair Retry

| Operation | Model | Input tokens | Output tokens | Cost |
| --- | --- | --- | --- | --- |
| Planner (re-prompt with violations) | Mid-tier | 6,500 | 6,000 | $0.0046 |

Hard-capped at **2 repair attempts** per cycle. Maximum additional cost: **$0.0092**.

### Reflection-Only Cycle (daily batch)

| Operation | Model | Input tokens | Output tokens | Cost |
| --- | --- | --- | --- | --- |
| Reflection per user | Mid-tier | 1,500 | 400 | $0.00047 |

### User-Facing Explanation Generation

| Operation | Model | Input tokens | Output tokens | Cost |
| --- | --- | --- | --- | --- |
| Explanation (per call) | Mid-tier | 1,000 | 300 | $0.00033 |

Approximately 3–5 explanations per active week → **~$0.0015 / week**.

## Per-User Monthly LLM Cost Estimate (Active User)

| Component | Frequency | Monthly Cost |
| --- | --- | --- |
| Onboarding (amortized over 6 months) | 1 / 6 mo | $0.015 |
| Replan cycles | ~4 / mo | $0.272 |
| Validation retries | ~3 / mo | $0.028 |
| Reflection batch | ~30 / mo | $0.014 |
| Explanations | ~15 / mo | $0.005 |
| **Total monthly LLM cost** | | **~$0.33 – $0.45** |

## Sensitivity Analysis

If assumptions are off by 2× in either direction:

- **Conservative (high-usage power user)**: ~$0.90 / month.
- **Aggressive (low-usage casual user)**: ~$0.15 / month.

These numbers are order-of-magnitude estimates with explicit assumptions. Real numbers must be measured in production. They must not be used for pricing decisions without validation.

## Total Infrastructure Cost (with all overhead)

| Component | Monthly Range |
| --- | --- |
| LLM | $0.33 – $0.90 |
| Database (Postgres + pgvector) | $0.10 – $0.30 |
| Background workers and queues | $0.05 – $0.15 |
| Calendar API (free at current scale) | $0 |
| Logging, observability, embedding refresh | $0.10 – $0.25 |
| **Total per active user per month** | **$0.60 – $1.60** |

Earlier informal targets ("$1 – $3 per active user per month, ceiling $5 – $10") are superseded by the table above. The new range reflects measured token budgets and the cost controls below.

## At-Scale Estimates (Caveats Apply)

| Active Users | Estimated Monthly Infrastructure |
| --- | --- |
| 1,000 | $600 – $1,600 |
| 10,000 | $6,000 – $16,000 |
| 100,000 | Requires renegotiated LLM pricing; likely $30,000 – $80,000 |

These are order-of-magnitude estimates with explicit assumptions. They are not pricing inputs.

## Cost Control Enforcement

- **Per-user hourly cap:** 5 LLM calls per hour.
- **Per-user monthly cap:** $2.00 LLM spend (5× expected; alert at 80%).
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

The token budgets and cost ranges in this document are computed from current pricing and assumed usage. Internal documentation must label them as estimates pending production validation. Do not use them for external pricing claims, customer commitments, or financial models without measured production data.

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
