# 07: Telemetry and Drift

## Principle

Telemetry captures enough information to improve scheduling and duration estimates without overcollecting sensitive data. The MVP is privacy-first.

The deterministic drift classifier decides drift type from observable behavior — never personality guesses. The policy engine selects the response. The LLM may explain the result to the user, but it must not classify drift in the MVP.

Drift detection and accountability are related but distinct:

- Drift classification identifies what kind of mismatch exists.
- The Accountability Policy Engine (`21-accountability-layer.md`) decides what intervention should happen.
- The LLM may explain the result to the user in friendly language.

## Privacy Rules

The MVP **must not** store:

- Raw calendar event titles.
- Raw calendar event descriptions.
- Unrelated calendar metadata.
- Sensitive user notes.
- Cross-user training data without opt-in.

The MVP **may** store:

- Free/busy blocks.
- Generated event IDs for app-created events.
- Task completion state.
- Scheduled duration.
- Actual duration.
- Reschedule count.

## Minimum Telemetry Schema

```json
{
  "telemetry_event_id": "tel_123",
  "task_id": "dp_002",
  "scheduled_duration_min": 90,
  "actual_duration_min": 135,
  "completed": true,
  "completion_timestamp": "2026-05-06T20:42:00-07:00",
  "user_reschedule_count": 2
}
```

See `../specs/telemetry.schema.md`.

## Drift Classifier Output

```json
{
  "drift_detected": true,
  "drift_type": "duration_underestimate",
  "confidence": 0.82,
  "evidence": {
    "median_actual_vs_predicted_ratio": 1.48,
    "affected_categories": ["dynamic_programming"],
    "sample_size": 6
  },
  "recommended_policy_action": "increase_duration_estimates_for_category"
}
```

## Drift Types and Deterministic Triggers

| Drift Type | Deterministic Trigger | Response |
| --- | --- | --- |
| `capacity_mismatch` | User completes <60% of scheduled weekly minutes for 2 cycles | Reduce weekly load or extend timeline |
| `duration_underestimate` | Median `actual / predicted` > 1.3 across at least 5 completed tasks | Increase duration multiplier for category |
| `duration_overestimate` | Median `actual / predicted` < 0.7 across at least 5 completed tasks | Decrease duration multiplier |
| `topic_avoidance` | Same module missed or rescheduled >= 3 times while other modules complete | Split topic into smaller tasks or add review block |
| `external_conflict` | Misses correlate with calendar conflicts or manual reschedules | Reschedule, do not change curriculum |
| `low_engagement` | Many skipped tasks across categories | Ask user to adjust goal or scope |
| `dependency_blocked` | Downstream tasks blocked by an incomplete prerequisite | Reschedule prerequisite first |
| `calendar_fragmentation` | Total free time exists, but largest block is too small for deep-work tasks | Split tasks or ask user to open larger blocks |
| `accountability_mismatch` | User repeatedly misses tasks but declines interventions | Ask user to revise accountability contract |
| `sponsor_pressure_mismatch` | User disables sponsor reporting after repeated reports | Reduce external reporting and switch to private recovery mode |

## Decision vs Explanation

- **Bad**: LLM decides the user is lazy and needs pressure.
- **Good**: Rule-based classifier detects `low_engagement`. Policy engine selects `recovery_checkin`. LLM explains the recovery options in a supportive tone.

Drift classification (this file) identifies the mismatch. The Accountability Policy Engine (`21-accountability-layer.md`) decides whether, how, and to whom the system responds.

## Responses

- Emit `drift_event` with `drift_type`, `reason_code`, evidence, and recommended action.
- Route to `drift_detected`, then `replan_required` if action is needed.
- Require user approval before changing calendar events.
- Use deterministic multipliers for future duration estimates before considering model changes (see `17-duration-estimation.md`).

## Privacy Positioning

Data-rich personalization is a later opt-in feature. The MVP must work and earn user trust with minimum telemetry first.

## Drift Threshold Calibration

### Threshold Honesty

All numeric thresholds above (1.3 duration ratio, 5-task minimum, 60% completion floor, 2-cycle window, etc.) are **initial defaults, not validated parameters**. They were chosen to be plausible, not optimal. They will be wrong for some users and right for others, and there is no data yet to know which.

Internal documentation and engineering reviews must mark drift thresholds as "uncalibrated heuristics — pending calibration." The product must not present them as tuned values until calibration is complete.

### Calibration Trigger

Calibration runs once the system has accumulated **>= 50 active users with >= 4 weeks of telemetry each**.

### Calibration Methodology

1. **Backtesting.** For each threshold, simulate alternative values against historical telemetry. For `duration_underestimate` triggering at ratio > 1.3 with sample >= 5, also simulate at:
   - > 1.2 / >= 4
   - > 1.4 / >= 6
   - > 1.5 / >= 3

   For each simulation, measure:
   - **True positive rate** — drift was correctly flagged and intervention helped.
   - **False positive rate** — drift was flagged but intervention disrupted a working plan.
   - **Time-to-detection** — how many tasks before drift was caught.
2. **Outcome scoring.**
   - "Helped" — in the 2 cycles following intervention, completion rate increased by **> 10%** or duration prediction error decreased by **> 15%**.
   - "Disrupted" — user reverted, manually edited **> 50%** of remediated tasks, or churned within 7 days.
3. **Threshold optimization.** For each drift type, select thresholds that maximize `true_positive_rate − (false_positive_rate * 2)`. False positives are weighted **2×** because disrupting a working plan is worse than missing a problem the user can self-correct.

### Per-User Threshold Adaptation (Phase 3+)

Users have different tolerances. Some want aggressive intervention; others want to be left alone. After Phase 2, expose a sensitivity preference (for example, "How aggressive should we be about adjusting your plan?") that scales global thresholds:

- **Conservative** — thresholds * 1.3 (intervene less often).
- **Balanced** — thresholds * 1.0 (default).
- **Aggressive** — thresholds * 0.75 (intervene sooner).

Per-user scaling does not change the deterministic classifier; it only multiplies thresholds before classification.

### Threshold Change Log

All threshold modifications must be recorded in `drift_threshold_history`:

- `drift_type`
- `threshold_field`
- `prior_value`
- `new_value`
- `effective_at`
- `justification`
- `dataset_reference`

No silent threshold changes between releases. Every change is auditable.

### MVP Disclosure

Until calibration is complete, the system must not present drift detection as "tuned" or "data-driven." Internal docs, engineering reviews, and any user-facing tooltip referring to thresholds must describe them as heuristic priors.

## Psychological Labeling Restrictions

The system must not store psychological labels such as `lazy`, `irresponsible`, `anxious`, `avoidant`, or `unmotivated`. These labels are trust-breaking, legally risky, and almost always wrong when derived from a handful of missed tasks.

The system may store behavioral state such as:

- `missed_tasks_7d`
- `completion_rate_14d`
- `reschedule_count_7d`
- `behind_schedule_percent`
- `checkin_completion_status`
- `recovery_option_selected`

Behavioral state is sufficient for scheduling and accountability without overreaching into sensitive inference. The LLM must not generate prose that implies a psychological diagnosis based on telemetry — wording should describe behavior, not identity.

## Related Docs

- `02-state-machine.md`
- `09-cost-and-metrics.md`
- `12-edge-case-policy-engine.md`
- `17-duration-estimation.md`
- `21-accountability-layer.md`
- `../specs/telemetry.schema.md`
- `../specs/drift-event.schema.md`
- `../specs/motivation-profile.schema.md`
- `../decisions/ADR-0004-no-per-user-ml-model-in-mvp.md`
