# Recommitment Event Schema

## Owner

Recommitment flow (`../axioms/21-accountability-layer.md`, intervention table:
"Direct nudge" and "Accountability reset").

## Consumers

Accountability Policy Engine (recommitment pending/resolved), plan versioning
flow, audit log, completion dashboard.

## Purpose

When the user repeatedly misses tasks, the system may ask for **explicit
recommitment**: re-approval of the plan, timeline, or intensity. This spec
defines the request/response pair:

- `RecommitmentRequest` — the system's ask, emitted with reason code
  `USER_RECOMMITMENT_REQUIRED` alongside a `recommitment_requested` nudge.
- `RecommitmentEvent` — the user's explicit, append-only answer.

Recommitment never mutates anything by itself. `keep_plan` records explicit
re-approval of the active plan version; every `revise_*` choice routes into
the existing draft → validation → diff → approval pipeline (axiom 15). The LLM
may phrase the ask supportively; it never chooses for the user.

## JSON Example

```json
{
  "recommitment_request_id": "recommit_req_001",
  "user_id": "user_123",
  "plan_version": "plan_004",
  "decision_id": "intv_002",
  "reason_code": "USER_RECOMMITMENT_REQUIRED",
  "requested_at": "2026-05-10T20:00:06-07:00"
}
```

```json
{
  "recommitment_event_id": "recommit_evt_001",
  "recommitment_request_id": "recommit_req_001",
  "user_id": "user_123",
  "plan_version": "plan_004",
  "choice": "revise_timeline",
  "created_at": "2026-05-11T09:30:00-07:00"
}
```

## Field Definitions

`RecommitmentRequest`:

| Field | Type | Purpose |
| --- | --- | --- |
| `recommitment_request_id` | string | Primary key. |
| `user_id` | string | Subject. |
| `plan_version` | string | Active plan version the user is asked to recommit to. |
| `decision_id` | string | The `InterventionDecision` that triggered the ask. |
| `reason_code` | enum `ReasonCode` | Always `USER_RECOMMITMENT_REQUIRED`. |
| `requested_at` | datetime | Timezone-aware. |

`RecommitmentEvent`:

| Field | Type | Purpose |
| --- | --- | --- |
| `recommitment_event_id` | string | Primary key; unique, used for dedup. |
| `recommitment_request_id` | string | The request being answered. |
| `user_id` | string | Subject. |
| `plan_version` | string | Plan version the choice applies to. |
| `choice` | enum | `keep_plan`, `revise_timeline`, `revise_intensity`, `revise_goal` |
| `created_at` | datetime | Timezone-aware. |

## Choice Semantics (Deterministic Next Action)

| Choice | Next action |
| --- | --- |
| `keep_plan` | Record explicit re-approval of the active plan version; no artifact changes. |
| `revise_timeline` | Route to the recovery/replan path (`extend_timeline` mode); draft plan version follows validation → diff → approval. |
| `revise_intensity` | Route to the recovery/replan path (`scope_reduction` mode); same pipeline. |
| `revise_goal` | Route to profile update; `PROFILE_MAJOR_CHANGE` invalidation policy applies (axiom 12). |

## Required Fields

All fields on both objects.

## Validation Rules

- `reason_code` on a request must be `USER_RECOMMITMENT_REQUIRED`.
- All timestamps timezone-aware.
- Events are append-only; answering the same request twice is rejected by the
  store (the first explicit answer stands; a changed mind is a new request).

## Invalid Examples

```json
{ "reason_code": "MISSED_TASK_THRESHOLD_REACHED" }
```

Reason: a recommitment request carries exactly `USER_RECOMMITMENT_REQUIRED`;
the missed-task code belongs to the nudge that delivered it.

```json
{ "choice": "give_up" }
```

Reason: not a recommitment choice; abandoning the plan is a plan-lifecycle
action, not an accountability response.

## Relationships

- Requests are emitted by the recommitment flow when a
  `recommitment_requested` nudge goes out (`nudge.schema.md`).
- `revise_*` choices feed the recovery-plan path and axiom 15 plan
  versioning.
- Golden scenario coverage: part of the direct-nudge escalation
  (scenario 16 family) and the accountability-reset intervention.

## Related Docs

- `nudge.schema.md`
- `accountability-intervention.schema.md`
- `plan-diff.schema.md`
- `../axioms/15-plan-versioning-and-diffs.md`
- `../axioms/21-accountability-layer.md`
