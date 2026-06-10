# Accountability State Schema

## Owner

Accountability State projection (`../axioms/21-accountability-layer.md`).

## Consumers

Accountability Policy Engine, completion dashboard, sponsor report generator,
drift composition root.

## Purpose

`AccountabilityState` is the deterministic projection of telemetry and
check-in events against the accountability contract. Axiom 21: it "must be
recomputed from source events, never edited in place." It answers, with
numbers, "is this user behind?" — the question the LLM is forbidden from
answering.

The projection is a pure function of caller-scoped event windows. Following
the `DriftInput` precedent, the **caller** scopes telemetry to the 7- and
14-day windows and supplies plan-to-date scheduled/completed minutes; the
projection never reads stores or clocks beyond the injected `computed_at`.

## JSON Example

```json
{
  "user_id": "user_123",
  "plan_id": "plan_004",
  "completion_rate_7d": 0.62,
  "completion_rate_14d": 0.55,
  "missed_tasks_7d": 3,
  "reschedule_count_7d": 4,
  "behind_schedule_percent": 18,
  "weekly_checkin_completed": false,
  "current_status": "slightly_behind",
  "recommended_intervention": "send_user_nudge",
  "sponsor_report_allowed": true,
  "sponsor_report_level": "summary_only",
  "computed_at": "2026-05-10T20:00:00-07:00"
}
```

Note: axiom 21's illustrative example shows `recommended_intervention:
"recovery_checkin"`; this spec normalizes the field to the
`AccountabilityAction` enum (`accountability-intervention.schema.md`) so the
state and the policy engine share one action vocabulary.

## Field Definitions

| Field | Type | Purpose |
| --- | --- | --- |
| `user_id` | string | Subject. |
| `plan_id` | string | Active plan projected against. |
| `completion_rate_7d` | number 0–1 | Completed ÷ total telemetry events in the 7-day window; `1.0` when the window is empty (no evidence of being behind). |
| `completion_rate_14d` | number 0–1 | Same over the 14-day window. |
| `missed_tasks_7d` | integer ≥ 0 | Events with `completed: false` in the 7-day window. |
| `reschedule_count_7d` | integer ≥ 0 | Sum of `user_reschedule_count` over the 7-day window. |
| `behind_schedule_percent` | integer 0–100 | See formula below. |
| `weekly_checkin_completed` | boolean | True when the current cycle's check-in exists, or check-ins are disabled. |
| `current_status` | enum `AccountabilityStatus` | Deterministic; see threshold table. |
| `recommended_intervention` | enum `AccountabilityAction` or null | The policy engine's chosen private-lane action; null when no rule matched or the contract is inactive. |
| `sponsor_report_allowed` | boolean | Contract snapshot at computation time. |
| `sponsor_report_level` | enum `SponsorVisibility` | Contract snapshot. |
| `computed_at` | datetime | When the projection ran. |

## Behind-Schedule Formula

Given caller-supplied plan-to-date minutes:

```text
behind_schedule_percent =
  0                                            if scheduled_minutes_due == 0
  round(100 * max(0, scheduled_minutes_due - completed_minutes_due)
        / scheduled_minutes_due)               otherwise
```

Clamped to `[0, 100]`. Overshooting (completing more than scheduled) clamps to
0 rather than going negative. Rounding is round-half-up to match the
duration-calibration convention.

## Status Thresholds (Deterministic, Heuristic Priors)

Evaluated top-down, first match wins, using the contract's effective
behind-schedule threshold `T` and the disengagement floor `0.2`:

| Order | Status | Condition |
| --- | --- | --- |
| 1 | `disengaged` | `completion_rate_14d < 0.2` |
| 2 | `far_behind` | `behind_schedule_percent >= 2 * T` |
| 3 | `behind` | `behind_schedule_percent >= T` |
| 4 | `slightly_behind` | `behind_schedule_percent >= ceil(T / 2)` OR `missed_tasks_7d >= 1` |
| 5 | `on_track` | otherwise |

With the axiom 21 example values (`T = 20`, behind 18%, 3 missed, 14-day rate
0.55) this yields `slightly_behind`, matching the axiom. The `0.2`
disengagement floor and the `T/2` slightly-behind band are heuristic priors
until calibrated.

No psychological labels: `current_status` describes schedule position, never
identity (axiom 07, Psychological Labeling Restrictions).

## Required Fields

All fields. `recommended_intervention` is nullable but always present.

## Validation Rules

- Rates in `[0, 1]`; counts ≥ 0; `behind_schedule_percent` in `[0, 100]`.
- If `sponsor_report_allowed` is false, `sponsor_report_level` must be `none`;
  if true, it must not be `none`.
- `computed_at` must be timezone-aware.
- The state object is frozen; recomputation produces a new object (axiom 21:
  never edited in place).

## Invalid Examples

```json
{ "completion_rate_7d": 1.3 }
```

Reason: a completion rate is a proportion in `[0, 1]`.

```json
{ "behind_schedule_percent": 130 }
```

Reason: percent is clamped to `[0, 100]` by the projection; a value outside
the range is a producer bug.

```json
{ "sponsor_report_allowed": false, "sponsor_report_level": "summary_only" }
```

Reason: a disallowed sponsor path cannot carry a visibility level.

## Relationships

- Produced by `project_accountability_state` (`accountability/`), consuming
  caller-scoped `TelemetryEvent` windows, `CheckinEvent` presence, and the
  `AccountabilityContract`.
- `recommended_intervention` is filled from the policy engine's decision
  (`accountability-intervention.schema.md`).
- Surfaced by the completion dashboard CLI.

## Related Docs

- `telemetry.schema.md`
- `checkin-event.schema.md`
- `accountability-contract.schema.md`
- `accountability-intervention.schema.md`
- `../axioms/07-telemetry-and-drift.md`
- `../axioms/21-accountability-layer.md`
