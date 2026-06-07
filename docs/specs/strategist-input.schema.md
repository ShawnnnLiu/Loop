# Strategist Input Schema

## Owner

The Strategist composition root (Phase 5b).

## Consumers

`StrategistNode` — this is the validated bundle assembled and re-validated at the
node boundary, so a malformed claim set or constraint set is caught before
generation rather than three layers deep.

## Purpose

The single validated input object handed to the Strategist: the user profile, the
scored source claims it may cite, and the strategy constraints it must respect.

## JSON Example

```json
{
  "user_profile": { "...": "a full user_profile object (see user-profile.schema.md)" },
  "source_claims": [ { "...": "scored SourceClaim objects (see source-claim.schema.md)" } ],
  "strategy_constraints": { "max_modules": 12 }
}
```

## Field Semantics

| Field | Purpose |
| --- | --- |
| `user_profile` | The full `UserProfile` (required; see `user-profile.schema.md`) |
| `source_claims` | Scored `SourceClaim`s the Strategist may cite (default `[]`); `claim_id`s must be unique |
| `strategy_constraints` | The bounds the proposal must respect (default: spec defaults; see `strategy-constraints.schema.md`) |

## Invariants

- `user_profile` is required and must itself be a valid `UserProfile`.
- `source_claims` `claim_id` values are unique within the bundle.
- Each `SourceClaim` is independently valid.
- Unknown fields are rejected (`extra="forbid"`).

## Invalid Examples

```json
{ "source_claims": [] }
```

Reason: `user_profile` is required.

```json
{
  "user_profile": { "...": "valid" },
  "source_claims": [ { "claim_id": "c1", "...": "..." }, { "claim_id": "c1", "...": "..." } ]
}
```

Reason: duplicate `source_claim` `claim_id`.

## Related Docs

- `user-profile.schema.md`
- `source-claim.schema.md`
- `strategy-constraints.schema.md`
- `syllabus-units.schema.md`
