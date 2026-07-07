# Resume Extraction Schema

## Owner

`ResumeIntakeNode` (the fifth allowed LLM node — see
`../axioms/01-system-boundaries.md`).

## Consumers

Onboarding UI (display + edit), tests. Never a deterministic consumer:
nothing routes on this object. It reaches storage only after the user edits
and confirms it through `POST /api/onboard`.

## Purpose

`ResumeExtraction` is the schema-bound proposal the ResumeIntakeNode returns
from a pasted résumé plus draft onboarding answers: experience entries,
skills, strengths, inferred weak spots, and target-company categories. It is
a *candidate* for user-editable profile fields — the human review gate plus
deterministic schema validation are the disposal side of "LLMs propose,
deterministic infrastructure disposes."

All lists default empty: **empty over fabrication**. A sparse résumé must
produce a sparse extraction, not invented content.

## JSON Example

```json
{
  "experience": [
    {
      "title": "Senior Backend Engineer",
      "organization": "Acme Corp",
      "summary": "Led the billing platform team; Python and Go services."
    }
  ],
  "skills": ["Python", "Go", "PostgreSQL", "Kubernetes"],
  "known_strengths": ["distributed systems", "API design"],
  "inferred_weak_spots": ["System design", "Dynamic programming"],
  "target_company_categories": ["fintech", "developer-tools companies"]
}
```

## Field Definitions

| Field | Type | Bounds | Provenance tier |
| --- | --- | --- | --- |
| `experience` | `list[ExperienceItem]` | max 20 items | extracted (groundedness-checked) |
| `skills` | `list[str]` | max 40 items, each 1–60 chars | extracted (groundedness-checked) |
| `known_strengths` | `list[str]` | max 15 items, each 1–60 chars | inferred (résumé-anchored generalization) |
| `inferred_weak_spots` | `list[str]` | max 15 items, each 1–60 chars | inferred (gap vs draft goal/role) |
| `target_company_categories` | `list[str]` | max 8 items, each 1–60 chars | suggested |

`ExperienceItem` (defined in `user-profile.schema.md` — it is profile
vocabulary; this contract imports it):

| Field | Type | Bounds |
| --- | --- | --- |
| `title` | string | required, 1–120 chars |
| `organization` | string or null | optional; 1–120 chars when present |
| `summary` | string or null | optional; 1–280 chars when present |

## Provenance Is Structural

The three provenance tiers map to field groups, not to per-item scores:
`experience`/`skills` are *extracted*, `known_strengths`/
`inferred_weak_spots` are *inferred*, `target_company_categories` is
*suggested*. There are **no confidence values anywhere** — LLMs do not
assign confidence (axioms 00/08); the UI labels sections, and nothing
routes on provenance.

## Invariants

Spec-level invariants, mirrored one-for-one by the deterministic
post-validator in the adapter (listed here so prompt rules, validator, and
spec cannot drift):

1. **Groundedness.** Every `ExperienceItem.title` and `.organization`, and
   every `skills` item, appears in the source résumé text
   (case-insensitive, whitespace-normalized substring match).
2. **No company names, no prestige tiers.** No
   `target_company_categories` item contains an extracted organization
   string or a prestige-ranking term. Denylist (single source of truth is
   the code constant in the adapter; quoted here verbatim): `mid-tier`,
   `low-tier`, `bottom`, `mediocre`, `second-rate`, `b-tier`.
3. **Uniqueness.** Case-insensitive uniqueness within each list
   (contract-enforced). For `experience`, the identity is the
   `(title, organization)` pair, compared case-insensitively.
4. **No confidence numbers anywhere**; the field grouping IS the
   provenance (structurally guaranteed: no such field exists and
   `extra="forbid"` rejects riders).
5. **Closed weak-spot vocabulary.** Every `inferred_weak_spots` item must
   resolve (via the deterministic normalizer) to a taxonomy entry in the
   input's `allowed_weak_spots` (see `resume-intake-input.schema.md` and
   `skill-taxonomy.schema.md`). Membership is enforced in the repair loop;
   persistent violation surfaces as `REPAIR_LIMIT_EXCEEDED`.

Invariants 1, 2, and 5 need the résumé text / allowed vocabulary and are
checked by the adapter's post-validator inside the bounded repair loop
(never silently dropped — typed `reason_code` on failure). Invariants 3 and
4 are enforced by the Pydantic contract itself.

`skills` items are **surface strings** as they appear in the résumé. The
node is never asked to emit canonical vocabulary names; deterministic
normalization onto the skill taxonomy happens at the service layer after
the node returns (see `skill-taxonomy.schema.md`).

## Required Fields

None — every field is a list defaulting to empty. An all-empty extraction
is valid (and correct for an unparseable or off-domain résumé).

## Validation Rules

- List length bounds as in the field table.
- Item length bounds as in the field table; items must be non-empty.
- Case-insensitive uniqueness within each list.
- Unknown fields are rejected (`extra="forbid"`).

## Invalid Examples

```json
{ "skills": ["Python", "python"] }
```

Reason: case-insensitive duplicate within a list.

```json
{ "experience": [{ "title": "" }] }
```

Reason: empty title.

```json
{ "skills": ["Python"], "confidence": 0.9 }
```

Reason: unknown field — confidence values are structurally rejected.

## Related Docs

- `../axioms/01-system-boundaries.md`
- `../axioms/03-data-contracts.md`
- `resume-intake-input.schema.md`
- `skill-taxonomy.schema.md`
- `user-profile.schema.md`
