# Prose Attachment Schema

## Owner

The app cycle (`../axioms/07-telemetry-and-drift.md` reflection flow,
`../axioms/22-llm-evaluation-and-observability.md` prose-node outputs). The
cycle persists exactly one record per prose-node output it surfaces to the
user: a `ReflectionSummary` generated on drift at ingest, or a
`UserFacingExplanation` generated on a terminal validation failure.

## Consumers

Read projections only: the status/banner surfaces (a parked run's "why" at
resume time), the reflection-history view, and — as *advisory prompt context
only* — the reflection node's own continuity block and the replan Planner's
behavioral-hints block (UX pass D2).

## Purpose

Before this record existed, prose the product had already generated and paid
for was returned once and discarded: `IngestResult.reflection` was rendered
(at most) and gone, and a user returning to a run parked in
`ERROR_REQUIRES_USER` saw only a bare reason code. `ProseAttachmentRecord`
makes those sentences durable so the product can say *what it already said* —
continuity across sessions is what separates a coach from a report.

## Control-Plane Rule

Prose attachments are **display and advisory-context data, never control
plane**. No routing, validation, scheduling, approval, or write decision may
read this record (the core thesis: LLM prose must not control workflow
state). The typed `reason_code` field is a *copy* of the run's typed cause for
display alongside the prose — the run record remains the authoritative source.

## Privacy Rule

`summary` and `detail` are LLM- or deterministic-node-generated sentences that
passed the psych-label post-validator before reaching the user. They must
never contain raw calendar titles/descriptions (nothing upstream has them) or
credentials. Records are derived personal data: `delete_for_user` exists so a
user can erase them, mirroring ADR-0007's disposition-store deletion surface.

## Fields

| field | type | notes |
| --- | --- | --- |
| `prose_attachment_id` | str | unique, append-only identity |
| `user_id` | str | owner |
| `run_id` | str | the supervisor run the prose was generated for |
| `plan_version` | str \| null | plan context when one existed |
| `kind` | `"reflection"` \| `"explanation"` | which node produced it |
| `summary` | str (min 1) | the one-line user-facing sentence |
| `detail` | list[str] | supporting lines (may be empty) |
| `reason_code` | ReasonCode \| null | typed cause the prose explains (copy) |
| `created_at` | datetime (tz-aware) | injected clock |

## Validation Rules

* `created_at` must be timezone-aware.
* Unknown fields are rejected (`extra="forbid"`).
* Append-only store; duplicate `prose_attachment_id` is an error.

## JSON Example

```json
{
  "prose_attachment_id": "prose_001",
  "user_id": "user_123",
  "run_id": "run_123",
  "plan_version": "v3",
  "kind": "reflection",
  "summary": "Practice tasks are taking longer than planned.",
  "detail": ["Recent dynamic-programming sessions ran about 40% over."],
  "reason_code": "DRIFT_DURATION_UNDERESTIMATE",
  "created_at": "2026-07-04T09:00:00-07:00"
}
```
