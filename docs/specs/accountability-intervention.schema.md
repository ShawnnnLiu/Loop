# Accountability Intervention Schema

## Owner

Accountability Policy Engine (`../axioms/21-accountability-layer.md`).

## Consumers

Nudge delivery, recovery-plan flow, sponsor report generator, recommitment
flow, audit log, completion dashboard.

## Purpose

`InterventionDecision` is the auditable output of one Accountability Policy
Engine evaluation: which policies were checked, what each observed, which one
matched, and what action follows. Axiom 21: policies are evaluated in order,
the first matching policy chooses the action, and **every rule evaluation is
logged**. The LLM is forbidden from evaluating or reordering policies.

## Two Lanes

The engine evaluates two independent lanes:

- **Private lane** (ordered, first match wins): `missed_task_warning`,
  `recovery_plan`, `weekly_checkin_required`, `scope_reduction`. The result is
  `action`, the at-most-one private intervention.
- **Sponsor lane** (single rule): `sponsor_summary`. The result is
  `sponsor_action`, evaluated independently because a sponsor report is
  *additive to* — never a replacement for — the private intervention.

This is required by the golden scenarios: scenario 16 (2 missed tasks → nudge,
no sponsor report) and scenario 17 (4 missed tasks + sponsor enabled → nudge
threshold also exceeded, yet a sponsor draft is expected) cannot both hold
under one flat first-match list. Scenario 18's note already assigns the
sponsor-path classification to this engine separately from the private nudge.

An inactive contract short-circuits **both** lanes with
`ACCOUNTABILITY_CONTRACT_INACTIVE` and an empty evaluation list (golden
scenario 24).

## Policy Table (Private Lane Order)

| # | Policy | Condition (effective contract values) | Action | Reason code |
| --- | --- | --- | --- | --- |
| 1 | `missed_task_warning` | `missed_tasks_7d >= effective_missed_task_escalation_threshold` | `send_user_nudge` | `MISSED_TASK_THRESHOLD_REACHED` |
| 2 | `recovery_plan` | `behind_schedule_percent >= effective_behind_schedule_intervention_threshold_pct` | `generate_recovery_plan_draft` | `BEHIND_SCHEDULE_THRESHOLD_REACHED` |
| 3 | `weekly_checkin_required` | check-ins enabled AND no check-in this cycle | `create_weekly_checkin_prompt` | `CHECKIN_DUE`, or `CHECKIN_MISSED` past the grace window |
| 4 | `scope_reduction` | `completion_rate_14d < low_completion_rate_floor` | `suggest_scope_reduction` | `LOW_COMPLETION_RATE` |

Sponsor lane:

| Policy | Condition | Action | Reason code |
| --- | --- | --- | --- |
| `sponsor_summary` | `missed_tasks_7d >= 4` AND `sponsor_reporting_allowed` AND level != `none` | `generate_sponsor_summary_draft` | `SPONSOR_REPORT_PENDING` |

The sponsor-lane missed-task floor of `4` is a fixed heuristic prior (axiom 21
policy table; golden scenario 17), intentionally *not* user-scaled: external
visibility must not get easier to trigger than the axiom's published floor.

## JSON Example

```json
{
  "decision_id": "intv_001",
  "user_id": "user_123",
  "plan_id": "plan_004",
  "contract_id": "acct_001",
  "action": "send_user_nudge",
  "reason_code": "MISSED_TASK_THRESHOLD_REACHED",
  "policy_name": "missed_task_warning",
  "sponsor_action": null,
  "sponsor_reason_code": null,
  "evaluations": [
    {
      "policy_name": "missed_task_warning",
      "matched": true,
      "observed_value": 3,
      "threshold_value": 2
    },
    {
      "policy_name": "recovery_plan",
      "matched": false,
      "observed_value": 18,
      "threshold_value": 20
    },
    {
      "policy_name": "weekly_checkin_required",
      "matched": false,
      "observed_value": 1,
      "threshold_value": 1
    },
    {
      "policy_name": "scope_reduction",
      "matched": false,
      "observed_value": 0.55,
      "threshold_value": 0.5
    },
    {
      "policy_name": "sponsor_summary",
      "matched": false,
      "observed_value": 3,
      "threshold_value": 4
    }
  ],
  "decided_at": "2026-05-10T20:00:05-07:00"
}
```

## Field Definitions

`AccountabilityAction` enum: `send_user_nudge`,
`generate_recovery_plan_draft`, `create_weekly_checkin_prompt`,
`generate_sponsor_summary_draft`, `suggest_scope_reduction`.

`PolicyRuleEvaluation`:

| Field | Type | Purpose |
| --- | --- | --- |
| `policy_name` | string | Stable rule identifier from the policy table. |
| `matched` | boolean | Whether the condition held. |
| `observed_value` | number | The metric the rule observed. |
| `threshold_value` | number | The effective threshold it compared against. |

`InterventionDecision`:

| Field | Type | Purpose |
| --- | --- | --- |
| `decision_id` | string | Primary key. |
| `user_id` / `plan_id` / `contract_id` | string | Provenance. |
| `action` | `AccountabilityAction` or null | Private-lane outcome; null when nothing matched or contract inactive. |
| `reason_code` | `ReasonCode` or null | Paired with `action`; `ACCOUNTABILITY_CONTRACT_INACTIVE` on the short circuit. |
| `policy_name` | string or null | Private-lane rule that matched. |
| `sponsor_action` | enum or null | Only ever `generate_sponsor_summary_draft` or null. |
| `sponsor_reason_code` | `ReasonCode` or null | `SPONSOR_REPORT_PENDING` when fired; `ACCOUNTABILITY_CONTRACT_INACTIVE` on the short circuit; null otherwise. |
| `evaluations` | list | Every rule evaluated, both lanes, in table order. Empty only on the inactive short circuit. |
| `decided_at` | datetime | Timezone-aware. |

## Validation Rules

- `action` non-null ⇔ `policy_name` non-null, and requires `reason_code`
  non-null.
- `action` null with `reason_code` `ACCOUNTABILITY_CONTRACT_INACTIVE` is the
  inactive short circuit: `evaluations` must be empty, `sponsor_action` null,
  `sponsor_reason_code` `ACCOUNTABILITY_CONTRACT_INACTIVE`.
- `action` null with `reason_code` null means "no intervention": every
  evaluation must have `matched: false` for the private-lane rules.
- `sponsor_action` non-null requires `sponsor_reason_code`
  `SPONSOR_REPORT_PENDING`.
- Active-contract decisions carry exactly 5 evaluations (4 private + 1
  sponsor) in policy-table order.
- `decided_at` must be timezone-aware.

## Invalid Examples

```json
{ "action": "send_user_nudge", "reason_code": null }
```

Reason: an action without its reason code breaks the typed-reason-code axiom.

```json
{ "action": null, "reason_code": "ACCOUNTABILITY_CONTRACT_INACTIVE", "evaluations": [{ "policy_name": "missed_task_warning", "matched": false, "observed_value": 0, "threshold_value": 2 }] }
```

Reason: the inactive short circuit must not evaluate (or log) any rules.

```json
{ "sponsor_action": "generate_sponsor_summary_draft", "sponsor_reason_code": null }
```

Reason: a fired sponsor lane must carry `SPONSOR_REPORT_PENDING`.

## Relationships

- Consumes `accountability-contract.schema.md` and
  `accountability-state.schema.md` plus the check-in evaluator's status.
- `send_user_nudge` flows to `nudge.schema.md` delivery; at or above the
  escalation threshold the nudge also requests recommitment
  (`recommitment-event.schema.md`).
- `generate_recovery_plan_draft` flows to the recovery-plan path
  (`plan-diff.schema.md`, axiom 15): always a new draft plan version, never
  in-place mutation.
- `generate_sponsor_summary_draft` flows to the Phase 3 sponsor report
  generator, which re-enforces permission and privacy gates itself.

## Related Docs

- `accountability-contract.schema.md`
- `accountability-state.schema.md`
- `nudge.schema.md`
- `recommitment-event.schema.md`
- `../axioms/12-edge-case-policy-engine.md`
- `../axioms/16-reliability-patterns.md`
- `../axioms/21-accountability-layer.md`
