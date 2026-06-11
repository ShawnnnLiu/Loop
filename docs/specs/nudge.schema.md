# Nudge Schema

## Owner

Nudge Delivery Service (`../axioms/21-accountability-layer.md`).

## Consumers

Audit log, completion dashboard, metrics, notification transport (wired in a
later phase, like the sponsor channel transport).

## Purpose

`NudgeRecord` is the append-only audit record for one private user nudge — the
`send_user_nudge` / `create_weekly_checkin_prompt` outcomes of the policy
engine. Nudges are user-private: no sponsor, parent, or external party is ever
addressed (golden scenario 16: "a private in-app nudge only").

The record stores **identifiers and outcome metadata only**. Nudge wording may
be LLM-generated at render time, but the message body is never stored here and
never becomes control-plane state.

Phase 6d makes tone deterministic at the selection level: the contract carries
a `nudge_tone_tier` derived from `pressure_tolerance`
(`accountability-contract.schema.md` "Tone Tier"), the delivery service stamps
that tier onto the record, and the LLM renders phrasing **within** the tier
(`UserFacingExplanationNode` lane). The tier is a closed enum — `gentle`,
`standard`, `direct` — never free text and never a psychological label; the
privacy filter still scans whatever the LLM renders.

## Quiet Hours And Channel (Deterministic)

Delivery must respect the contract's `nudge_channel_preference` and
`quiet_hours` with zero violations:

- The channel is always the contract's preference; the service never chooses.
- If the delivery instant falls inside quiet hours (overnight windows where
  `end < start` wrap midnight), the nudge is **deferred, not dropped**:
  `status: deferred_quiet_hours` with `deliver_at` set to the next quiet-hours
  `end` boundary in the user's timezone.
- Outside quiet hours, `deliver_at` equals the request instant.

Sending is an external side effect, so the path supports `dry_run` (status
`dry_run`, nothing sent). A sent nudge cannot be recalled, so as with sponsor
notifications there is no rollback status; safety is enforced before send
(contract active, quiet hours, channel).

## JSON Example

```json
{
  "nudge_id": "nudge_001",
  "user_id": "user_123",
  "plan_id": "plan_004",
  "decision_id": "intv_001",
  "reason_code": "MISSED_TASK_THRESHOLD_REACHED",
  "channel": "in_app",
  "tone_tier": "standard",
  "status": "deferred_quiet_hours",
  "recommitment_requested": false,
  "created_at": "2026-05-10T23:15:00-07:00",
  "deliver_at": "2026-05-11T08:00:00-07:00"
}
```

## Field Definitions

| Field | Type | Purpose |
| --- | --- | --- |
| `nudge_id` | string | Primary key; unique, used for dedup. |
| `user_id` | string | Recipient (always the subject; never a sponsor). |
| `plan_id` | string | Plan context. |
| `decision_id` | string | The `InterventionDecision` that triggered this nudge. |
| `reason_code` | enum `ReasonCode` | Trigger: `MISSED_TASK_THRESHOLD_REACHED`, `CHECKIN_DUE`, `CHECKIN_MISSED`, `LOW_COMPLETION_RATE`, or `USER_RECOMMITMENT_REQUIRED`. |
| `channel` | enum `NudgeChannel` | Always the contract's `nudge_channel_preference`. |
| `tone_tier` | enum: `gentle`, `standard`, `direct` | The contract's `nudge_tone_tier` at delivery time; the LLM renders within it (Phase 6d). |
| `status` | enum: `sent`, `deferred_quiet_hours`, `dry_run` | Outcome. |
| `recommitment_requested` | boolean | True when the nudge asks for explicit recommitment (direct nudge at/above the escalation threshold). |
| `created_at` | datetime | Request instant. |
| `deliver_at` | datetime | Actual/planned delivery instant. |

## Required Fields

All fields.

## Validation Rules

- `created_at` and `deliver_at` must be timezone-aware.
- `status: deferred_quiet_hours` requires `deliver_at > created_at`.
- `status: sent` or `dry_run` requires `deliver_at == created_at`.
- `reason_code` must be one of the five trigger codes listed above — a nudge
  is never created for sponsor or calendar reason codes.
- `recommitment_requested` may be true only when `reason_code` is
  `MISSED_TASK_THRESHOLD_REACHED` or `USER_RECOMMITMENT_REQUIRED`.

## Privacy Rule

No message body, task names, calendar titles, blocker text, or psychological
labels. Identifiers and outcome metadata only (same rule as
`notification-log.schema.md`).

## Invalid Examples

```json
{ "status": "sent", "created_at": "2026-05-10T23:15:00-07:00", "deliver_at": "2026-05-11T08:00:00-07:00" }
```

Reason: a sent nudge is delivered at its request instant; a future
`deliver_at` means it should have been `deferred_quiet_hours`.

```json
{ "reason_code": "SPONSOR_REPORT_PENDING" }
```

Reason: sponsor outcomes are never delivered as private nudges.

```json
{ "reason_code": "CHECKIN_DUE", "recommitment_requested": true }
```

Reason: a check-in prompt does not ask for recommitment; only the
escalation-level nudge does.

## Relationships

- Triggered by `accountability-intervention.schema.md` decisions.
- Channel/quiet-hours inputs come from `accountability-contract.schema.md`.
- A `recommitment_requested` nudge pairs with
  `recommitment-event.schema.md`.

## Related Docs

- `accountability-contract.schema.md`
- `accountability-intervention.schema.md`
- `notification-log.schema.md`
- `../axioms/16-reliability-patterns.md`
- `../axioms/21-accountability-layer.md`
