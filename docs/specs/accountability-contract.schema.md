# Accountability Contract Schema

## Owner

Accountability Contract Manager (`../axioms/21-accountability-layer.md`).

## Consumers

Accountability Policy Engine, check-in evaluator, nudge delivery, sponsor
report flow, completion dashboard.

## Purpose

`AccountabilityContract` is the deterministic, versioned derivation of a
`MotivationProfile` that the Accountability Policy Engine actually reads. It
exists separately from the profile because:

- The engine consumes **effective** thresholds (profile values scaled by
  pressure tolerance), and that scaling must be recorded, auditable state —
  not re-derived ad hoc inside rules.
- Disabling accountability is a first-class state (`active: false`) that must
  stop all interventions with `ACCOUNTABILITY_CONTRACT_INACTIVE` without
  touching the motivation profile or the active plan.
- The contract snapshots its source `profile_version`, so every intervention
  decision can be traced to the exact preferences that produced it.

The derivation is pure: the same profile always yields the same contract
(modulo identifiers and timestamps). The LLM never reads or writes this
object.

## JSON Example

```json
{
  "contract_id": "acct_001",
  "user_id": "user_123",
  "motivation_profile_id": "mot_001",
  "profile_version": "mot_v1",
  "active": true,
  "weekly_checkin_enabled": true,
  "weekly_checkin_day": "Sun",
  "weekly_checkin_time": "19:00",
  "effective_missed_task_escalation_threshold": 2,
  "effective_behind_schedule_intervention_threshold_pct": 20,
  "low_completion_rate_floor": 0.5,
  "checkin_grace_hours": 48,
  "recovery_mode_preference": "reschedule",
  "sponsor_reporting_allowed": false,
  "sponsor_visibility_level": "none",
  "sponsor_id": null,
  "nudge_channel_preference": "in_app",
  "nudge_tone_tier": "standard",
  "quiet_hours": { "start": "22:00", "end": "08:00" },
  "created_at": "2026-05-01T12:00:00-07:00",
  "updated_at": "2026-05-01T12:00:00-07:00"
}
```

## Field Definitions

| Field | Type | Purpose |
| --- | --- | --- |
| `contract_id` | string | Primary key. |
| `user_id` | string | Subject of the contract. |
| `motivation_profile_id` | string | Source profile. |
| `profile_version` | string | Exact profile version this contract was derived from. |
| `active` | boolean | False stops all interventions (`ACCOUNTABILITY_CONTRACT_INACTIVE`). |
| `weekly_checkin_enabled` | boolean | Copied from the profile. |
| `weekly_checkin_day` | enum `Mon`–`Sun` or null | Copied; required iff check-ins enabled. |
| `weekly_checkin_time` | `HH:MM` or null | Copied; required iff check-ins enabled. |
| `effective_missed_task_escalation_threshold` | integer 1–14 | Profile threshold after pressure-tolerance scaling. |
| `effective_behind_schedule_intervention_threshold_pct` | integer 5–50 | Profile threshold after pressure-tolerance scaling. |
| `low_completion_rate_floor` | number (0, 1) | `scope_reduction` trigger floor. Heuristic prior `0.5` (axiom 21 policy table); not user-scaled in the MVP. |
| `checkin_grace_hours` | integer 1–168 | Hours after the due instant before `CHECKIN_DUE` becomes `CHECKIN_MISSED`. Heuristic prior `48`. |
| `recovery_mode_preference` | enum | Copied from the profile. |
| `sponsor_reporting_allowed` | boolean | `profile.sponsor_enabled` snapshot. |
| `sponsor_visibility_level` | enum `SponsorVisibility` | Snapshot. |
| `sponsor_id` | string or null | Snapshot. |
| `nudge_channel_preference` | enum `NudgeChannel` | Snapshot. |
| `nudge_tone_tier` | enum: `gentle`, `standard`, `direct` | Deterministic tone tier derived from `pressure_tolerance` (Phase 6d, "Tone Tier" below). The LLM renders nudge phrasing within this tier; the tier itself never comes from prose. |
| `quiet_hours` | `QuietHours` | Snapshot. |
| `created_at` / `updated_at` | datetime | Timezone-aware. |

## Threshold Scaling (Deterministic, Heuristic Priors)

Scaling uses **pressure tolerance only**. `procrastination_risk` shapes LLM
nudge *tone*, never thresholds; `self_motivation_level` sets onboarding
defaults, not runtime scaling. Both restrictions keep the threshold path
single-knob and auditable.

| `pressure_tolerance` | Missed-task threshold | Behind-schedule threshold |
| --- | --- | --- |
| `low` | profile value + 1 | profile value + 5 |
| `medium` | profile value | profile value |
| `high` | profile value − 1 | profile value − 5 |

Results clamp to the profile's own valid ranges (`1–14`, `5–50`). Low pressure
tolerance intervenes *later* (softer), high tolerance *earlier*. These offsets
are heuristic priors until calibrated (axiom: validation and drift thresholds
are priors until telemetry justifies tuning).

## Tone Tier (Phase 6d, Deterministic)

The contract carries the tone tier the LLM must render nudge phrasing within
(`UserFacingExplanationNode` lane). Selection is a deterministic mapping from
`pressure_tolerance`; the LLM never picks the tier:

| `pressure_tolerance` | `nudge_tone_tier` |
| --- | --- |
| `low` | `gentle` |
| `medium` | `standard` |
| `high` | `direct` |

Tier values are a closed enum, never free text and never a psychological
label. The delivery service stamps the tier onto each `NudgeRecord`
(`nudge.schema.md`), and the privacy filter still scans rendered output.

## Threshold Adaptation (Phase 6d, Deterministic, Heuristic Priors)

Observed behavior may adapt the effective private-lane thresholds — within
the same clamps as derivation, and never touching the sponsor lane:

- Repeatedly declined accountability interventions (the caller-derived
  `declined_interventions` count, same observable the drift classifier
  reads) raise the private nudge thresholds: at **2+** declines the
  missed-task threshold rises by 1 and the behind-schedule threshold by 5
  percentage points; at **4+** declines, by 2 and 10 (the cap).
- Adapted values clamp to `[1, 14]` / `[5, 50]` — the derivation clamps.
- Adaptation produces a **new contract snapshot** (new `contract_id`, fresh
  timestamps) rebuilt through full validation; the prior snapshot is never
  mutated.
- The **sponsor floor of 4 is fixed** — it is a policy-engine constant, not
  a contract field, and adaptation cannot reach it.
- Every adaptation is auditable: the result records the observed count, the
  offsets applied, and the before/after thresholds. The policy engine itself
  is untouched; it reads effective thresholds exactly as before, so equal
  thresholds produce identical decisions.

All adaptation offsets and decline boundaries are uncalibrated heuristic
priors.

## Required Fields

All fields. `weekly_checkin_day` / `weekly_checkin_time` may be null only when
`weekly_checkin_enabled` is false; `sponsor_id` may be null only when
`sponsor_reporting_allowed` is false.

## Validation Rules

- Mirrors the motivation-profile sponsor consistency rules: if
  `sponsor_reporting_allowed` is true, `sponsor_visibility_level` must not be
  `none` and `sponsor_id` must be set; if false, the level must be `none`.
- Check-in day/time required iff `weekly_checkin_enabled`.
- `effective_missed_task_escalation_threshold` in `[1, 14]`.
- `effective_behind_schedule_intervention_threshold_pct` in `[5, 50]`.
- `low_completion_rate_floor` strictly between 0 and 1.
- `checkin_grace_hours` in `[1, 168]`.
- Timestamps timezone-aware; `updated_at` ≥ `created_at`.

## Invalid Examples

```json
{ "sponsor_reporting_allowed": true, "sponsor_visibility_level": "none" }
```

Reason: sponsor reporting allowed but visibility is `none`.

```json
{ "weekly_checkin_enabled": true, "weekly_checkin_day": null }
```

Reason: enabled check-ins require a cadence day and time.

```json
{ "effective_behind_schedule_intervention_threshold_pct": 60 }
```

Reason: above the maximum of `50`; scaling must clamp.

## Relationships

- Derived from `motivation-profile.schema.md` by
  `derive_accountability_contract` (pure function, `accountability/`).
- Read by the Accountability Policy Engine
  (`accountability-intervention.schema.md`) and the check-in evaluator.
- `active: false` is the deterministic kill switch required by golden
  scenario 24.

## Related Docs

- `motivation-profile.schema.md`
- `accountability-state.schema.md`
- `accountability-intervention.schema.md`
- `../axioms/12-edge-case-policy-engine.md`
- `../axioms/21-accountability-layer.md`
