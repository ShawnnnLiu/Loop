# Pathway Template Schema

## Owner

The deterministic pathway registry (narrative-pathways NP-B; registry module placement decided there).

## Consumers

Onboarding UI (pathway cards), the `narrative/` kernel (slot coverage, pathway fit, story progress), the Strategist constraints composition root, and operator views.

## Purpose

A `PathwayTemplate` is a curated narrative package a user can choose to build toward: a one-sentence story spine plus the evidence slots (pillars) a coherent version of that story needs.
Templates are canned, validated literals owned by the registry, exactly like `MilestoneTemplate`s (`milestone-template.schema.md`).
LLM research may draft candidate content, but human review is the curation gate (axiom 08 controlled-vocabulary wall); an LLM never produces a template at runtime.
Pathway fit and gap computation over these templates is deterministic (axiom 00); LLMs never rank pathways or assign fit.

## JSON Example

```json
{
  "pathway_id": "ai-integration-engineer",
  "pathway_schema_version": "pathway-template-v1",
  "career_track": "ai_engineer",
  "display_name": "AI-Integration Engineer",
  "spine": "Ships LLM-powered features into real products, end to end.",
  "audience_note": "Product teams adding AI capabilities; applied-AI startups.",
  "evidence_slots": [
    {
      "slot_id": "llm-feature-depth",
      "title": "LLM feature shipped in a real app",
      "required_kinds": ["project", "work"],
      "required_themes_any": ["applied-ml", "llm-integration"],
      "min_items": 1,
      "gap_module_hint": "Build and deploy one LLM-backed feature end to end",
      "branch_skill_ids": ["skill.llm-apis", "skill.rag", "skill.prompt-engineering"]
    },
    {
      "slot_id": "public-artifact",
      "title": "Public writeup or talk",
      "required_kinds": ["project", "research"],
      "required_themes_any": ["technical-writing"],
      "min_items": 1,
      "gap_module_hint": "Write up one project as a technical narrative",
      "branch_skill_ids": ["skill.technical-writing"]
    }
  ]
}
```

## Field Semantics

### `PathwayTemplate`

| Field | Purpose |
| --- | --- |
| `pathway_id` | Stable identifier; unique within the registry (registry-level invariant) |
| `pathway_schema_version` | Shape version, `milestone-template` discipline; `PathwaySelection.pathway_registry_version` pins the registry version a selection was made against |
| `career_track` | Member of the closed `CareerTrack` enum (`contracts/career_track.py`) - the same join key the skill taxonomy and corpus use. Tandem later generalizes this to an anchor union (track or major-cluster); the field is an anchor, not hard-coded to careers forever |
| `display_name` | Card title |
| `spine` | The one-sentence claim the story makes |
| `audience_note` | Who buys this story (kinds of roles/teams). Category language only - no company names, no prestige tiers |
| `evidence_slots` | Non-empty list of `EvidenceSlot`s with unique `slot_id`s; 4-6 slots is the content guideline |

### `EvidenceSlot`

| Field | Purpose |
| --- | --- |
| `slot_id` | Stable identifier, unique within a template |
| `title` | User-facing pillar name |
| `required_kinds` | Non-empty, unique subset of the closed `EvidenceKind` enum (`work`, `project`, `volunteering`, `leadership`, `research`, `award`, `coursework`); an evidence item can only fill this slot if its `kind` is a member |
| `required_themes_any` | Non-empty, case-insensitively unique theme list; an item matches when its `theme_tags` intersect this set. Every member must exist in the registry's theme vocabulary (registry-completeness test) |
| `min_items` | How many matched items fill the slot (`>= 1`; below it with at least one match is `partial`) |
| `gap_module_hint` | Display/prompt seed text for the Strategist's `unfilled_slots` projection; never control flow, never parsed |
| `branch_skill_ids` | Non-empty, unique skill ids (3-6 is the content guideline); each must resolve against the pinned skill taxonomy (registry-completeness test). Seed set for the knowledge-map generator (`06-knowledge-tree.md` / `07-tree-generation.md`); no control-plane effect |

## Theme Vocabulary (registry-owned)

Theme tags are broader than skills ("distributed-systems", "applied-ml", "developer-experience").
They deliberately do not join the skill taxonomy: taxonomy kinds are `language|framework|tool|concept|practice` and its per-track slices are prompt-budgeted at ~100 entries, which themes would bloat.
The theme vocabulary lives inside the pathway registry file and versions with it: the union of all themes any registered pathway references, plus a small track-tagged pool of non-slot themes for tagging breadth.
Target is <= ~30 themes per career track; the combined intake-prompt slice (taxonomy + themes) must stay inside the résumé-intake prompt budget (re-asserted in NP-C).
Same curation wall as the taxonomy (axiom 08): versioned literals, append-only versions, human review is the gate, LLMs never extend it.

## Contract vs. Registry Responsibility

The Pydantic contract (`backend/src/agentic_calendar/contracts/pathway_template.py`) enforces only shape and internal consistency: field types and bounds, non-empty unique lists, and unique `slot_id`s within a template.
Registry-level invariants live in the registry's tests (NP-B), mirroring `tests/templates/test_registry.py`:

- `pathway_id`s unique within the registry.
- Every `required_themes_any` member exists in the registry's theme vocabulary.
- Every `branch_skill_ids` member resolves against the pinned skill taxonomy.
- No prestige terms in any text field (the extraction adapter's denylist, reused as a registry test).

## Invariants

- `evidence_slots` is non-empty; `slot_id`s are unique within a template.
- `required_kinds` is non-empty and unique; every member is a valid `EvidenceKind`.
- `required_themes_any` is non-empty and case-insensitively unique.
- `branch_skill_ids` is non-empty and unique.
- `min_items >= 1`.
- Templates are deterministic literals; an LLM never produces one at runtime.

## Invalid Examples

```json
{
  "pathway_id": "p",
  "pathway_schema_version": "v1",
  "career_track": "ai_engineer",
  "display_name": "P",
  "spine": "s",
  "audience_note": "a",
  "evidence_slots": []
}
```

Reason: `evidence_slots` must be non-empty.

```json
{ "career_track": "underwater_basket_weaving" }
```

Reason: unknown career track - the enum is closed.

```json
{
  "evidence_slots": [
    { "slot_id": "dup", "...": "..." },
    { "slot_id": "dup", "...": "..." }
  ]
}
```

Reason: duplicate `slot_id` within a template.

## Related Docs

- `../axioms/00-product-thesis.md`
- `../axioms/03-data-contracts.md`
- `../axioms/08-rag-source-claims.md` (controlled-vocabulary wall)
- `milestone-template.schema.md` (the registry-of-literals pattern this copies)
- `pathway-selection.schema.md`
- `user-profile.schema.md`
- `skill-taxonomy.schema.md`
- `../implementation-plans/narrative-pathways/02-contracts-and-registry.md`
