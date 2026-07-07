# Resume Intake Input Schema

## Owner

App layer (built from the `POST /api/onboard/extract` request).

## Consumers

`ResumeIntakeNode` — validated at the node boundary, like
`StrategistInput`, so a malformed bundle is caught before generation.

## Purpose

`ResumeIntakeInput` is the validated bundle handed to the ResumeIntakeNode:
the pasted résumé, the draft answers from earlier wizard steps (all
optional — the wizard may be partially filled), and the allowed weak-spot
vocabulary the service resolved from the skill taxonomy.

This is the first LLM input in the system that exists **before any run**:
there is no plan, no run context. The service mints a `run_id` with prefix
`intake-` for the LLM call log (see `llm-call-log.schema.md`).

## JSON Example

```json
{
  "user_id": "user_123",
  "resume_text": "Senior backend engineer, 4 yrs Python/Go. Led billing platform...",
  "draft_context": {
    "goal": "Backend SWE interview prep",
    "target_role": "Backend SWE",
    "experience_level": "intermediate",
    "timeline_weeks": 10,
    "weekly_hours": 8
  },
  "allowed_weak_spots": ["System design", "Dynamic programming", "SQL"]
}
```

## Field Definitions

| Field | Type | Rules |
| --- | --- | --- |
| `user_id` | string | required, non-empty |
| `resume_text` | string | required, **50–40,000 chars** |
| `draft_context` | `DraftProfileContext` | defaults to all-empty |
| `allowed_weak_spots` | `list[str]` | default empty; each item non-empty, max 60 chars; case-insensitively unique |

`resume_text` bounds: a 3-char paste is a deterministic 422, not an LLM
call; 40,000 chars is a generous multi-page ceiling.

`DraftProfileContext` — every field optional (`null` when the wizard step
is unanswered):

| Field | Type | Rules |
| --- | --- | --- |
| `goal` | string or null | non-empty when present |
| `target_role` | string or null | non-empty when present |
| `experience_level` | enum or null | `beginner`, `intermediate`, `advanced` |
| `timeline_weeks` | int or null | `> 0` when present |
| `weekly_hours` | number or null | `> 0` and `<= 40` when present |

`allowed_weak_spots` is filled by the **service** from the track-relevant
slice of the skill taxonomy (`skill-taxonomy.schema.md`): the node never
imports the taxonomy kernel — the vocabulary arrives as plain data on this
contract, and the extraction's `inferred_weak_spots` must resolve to
members of it (membership enforced in the repair loop). Empty means "no
vocabulary restriction was resolvable"; the service fills it whenever the
taxonomy is available.

## Privacy and Injection Posture

`resume_text` is PII and untrusted input: it is sent to the LLM provider
as a labeled data-not-instructions block (the existing Strategist résumé
pattern), hashed — never stored raw — in the LLM call log, and persisted
only on the user's own profile record if the user confirms onboarding.
The extract path itself is persistence-free.

## Invalid Examples

```json
{ "user_id": "user_123", "resume_text": "too short" }
```

Reason: `resume_text` under 50 chars — deterministic rejection before any
LLM call.

```json
{ "user_id": "", "resume_text": "..." }
```

Reason: empty `user_id`.

```json
{ "user_id": "user_123", "resume_text": "...", "draft_context": { "weekly_hours": 50 } }
```

Reason: `weekly_hours` above 40.

## Related Docs

- `../axioms/01-system-boundaries.md`
- `../axioms/03-data-contracts.md`
- `resume-extraction.schema.md`
- `skill-taxonomy.schema.md`
- `llm-call-log.schema.md`
- `user-profile.schema.md`
