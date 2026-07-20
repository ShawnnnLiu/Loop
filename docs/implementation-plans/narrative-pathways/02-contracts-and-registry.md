# 02 · Contracts and Registry — The Deterministic Core

Every object here follows the spec-first workflow: `docs/specs/` doc →
Pydantic contract → valid/invalid fixtures → `make schemas` → tests. Shapes
below are proposals to be finalized in NP-A; bounds are heuristic priors
until calibrated, like every other threshold in the repo.

## 1. `EvidenceItem` — additive amendment to `ExperienceItem`

`user-profile.schema.md` / `contracts/` — the existing `experience` list
becomes the evidence inventory without a rename or migration:

| Field | Change | Semantics |
| --- | --- | --- |
| `title`, `organization`, `summary` | unchanged | as shipped |
| `kind` | **new**, default `work` | closed enum: `work · project · volunteering · leadership · research · award · coursework` |
| `theme_tags` | **new**, default `[]` | max 5 per item, each a member of the **theme vocabulary** (below); case-insensitively unique |

Defaults make every existing stored profile and fixture valid unchanged.
The list cap stays 20 in Loop (Tandem raises it — activity lists are long;
that bump is a Tandem-scoped spec change, noted in `05-…`).

Also new on the profile:

| Field | Semantics |
| --- | --- |
| `pathway_selection` | optional `PathwaySelection` (below); absent = user skipped, all downstream surfaces behave as today |

## 2. Theme vocabulary — closed, registry-owned

Theme tags are broader than skills ("distributed-systems", "applied-ml",
"developer-experience"; Tandem adds "healthcare", "community-service").
They deliberately do **not** join the skill taxonomy: taxonomy kinds are
`language|framework|tool|concept|practice`, its per-track slices are
prompt-budgeted at ~100 entries (`../career-track-expansion/
01-expansion-mechanics.md`), and themes would bloat exactly that slice.

Instead the theme vocabulary lives **inside the pathway registry file** and
versions with it: the global vocabulary is the union of all themes any
registered pathway references, plus a small track-tagged pool of
non-slot themes for tagging breadth. Target ≤ ~30 themes per career track —
they ride the same intake prompt as the weak-spot vocabulary, so the
combined slice must stay inside the RI prompt budget (re-assert in NP-C).

Same curation wall as the taxonomy (axiom 08): versioned literals,
append-only versions, human review is the gate, LLMs never extend it.

## 3. `PathwayTemplate` — new registry, `MilestoneTemplate` pattern

New spec `pathway-template.schema.md`; literals live beside the milestone
registry (`templates/registry.py` is the pattern; a sibling
`pathways/registry.py` or a second registry module in `templates/` — NP-B
decides, boundaries unchanged either way).

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

Invariants (mirroring the milestone-template contract's shape-vs-content
split — the contract enforces shape, the registry review owns content):

- `evidence_slots` non-empty (4–6 is the content guideline), `slot_id`s
  unique within a template, `pathway_id`s unique within the registry.
- `career_track` is a member of the closed `CareerTrack` enum
  (`contracts/career_track.py`) — the same join key the taxonomy and corpus
  use. Tandem generalizes this to an anchor union (track *or* major-cluster);
  the field is designed as an anchor, not hard-coded to careers forever.
- Every `required_themes_any` member exists in the registry's theme
  vocabulary (registry-completeness test, like
  `tests/templates/test_registry.py`).
- No prestige terms in any text field (reuse the extraction adapter's
  denylist as a registry test).
- `gap_module_hint` is display/prompt seed text, never control flow.
- `branch_skill_ids` (3–6 per slot, content guideline): each member
  resolves against the pinned skill taxonomy (registry-completeness test,
  like `required_themes_any`). They are the seed set the knowledge-map
  generator resolves to groups (`06-…` / `07-tree-generation.md`) and have
  no control-plane effect.
- Templates are deterministic literals; an LLM never produces one at runtime.

## 4. `PathwaySelection` — typed control-plane state

New spec `pathway-selection.schema.md`; stored on the profile only via the
existing confirm gate (`POST /api/onboard` at onboarding; the profile-update
path from Tuning thereafter):

| Field | Semantics |
| --- | --- |
| `pathway_id` | member of the registry |
| `pathway_registry_version` | pins which registry version the selection was made against (taxonomy-version discipline) |
| `selected_at` | timestamp |
| `slot_overrides` | optional explicit item↔slot assignments where the user corrected the deterministic mapping (item identity → `slot_id`) |

Registry version bumps never silently re-map a live selection: coverage is
always computed against the *pinned* version until the user re-confirms on
the current one (surfaced as a gentle prompt, never forced).

## 5. The `narrative/` kernel — deterministic fit, gaps, and slot states

New region package `backend/src/agentic_calendar/narrative/` (pure functions,
`prerequisites/` is the model; imports `contracts/` + `common/` only,
`.importlinter` row added):

- `slot_coverage(profile, template) -> per-slot {filled|partial|empty} + matched item ids` —
  an item matches a slot iff `item.kind ∈ required_kinds` and
  `theme_tags ∩ required_themes_any ≠ ∅`; `slot_overrides` win over the
  greedy default assignment (one item may fill only one slot; deterministic
  tie-break by slot order then item order).
- `pathway_fit(profile, template) -> filled_slots / total_slots` — the card
  ordering key. **No weights, no scores in v1**; ties break by registry
  order. If weighting ever proves necessary it enters `tuning.toml` like
  scheduler weights, not the LLM.
- `story_progress(profile, plan, template) -> slot states` — *in progress* =
  an active-plan module carries the slot's `evidence_slot_id`; *filled* =
  coverage says so from confirmed evidence.

Axiom line this adds (to axiom 00's deterministic-ownership list, NP-A):

> Pathway fit, narrative gap computation, and story progress are computed
> deterministically from confirmed evidence; LLMs do not assign fit.

## 6. Strategist plumbing

`strategy-constraints.schema.md` gains optional fields (defaults preserve
`{}`-is-valid):

| Field | Semantics |
| --- | --- |
| `pathway_id` | the selected pathway (absent = no pathway shaping) |
| `unfilled_slots` | list of `{slot_id, title, gap_module_hint}` computed by the kernel — the Strategist is told the gaps, not asked to find them |
| `max_slot_modules` | bound on slot-linked modules per syllabus (default small, e.g. 3) |

`syllabus-units.schema.md`: `SyllabusModule` gains optional
`evidence_slot_id`. Validation (new deterministic checks, existing
categories):

- `evidence_slot_id` set but no pathway selected → `PATHWAY_NOT_SELECTED`.
- `evidence_slot_id` not a slot of the selected pathway → `UNKNOWN_EVIDENCE_SLOT`.
- slot-linked module count > `max_slot_modules` → `SLOT_MODULE_LIMIT_EXCEEDED`.
- A slot-linked module must carry a non-empty `reason` naming the pillar
  (user-facing honesty; checked as non-empty only — prose is never parsed).

Planner/Scheduler are **untouched**: slot linkage flows through to tasks as
opaque module metadata; nothing schedules differently because of story state.

## 7. Profile update policy — new rows

`user-profile.schema.md` policy table:

| Profile Change | Invalidate Syllabus? | Invalidate Tasks? | Invalidate Schedule? | Invalidate Accountability Contract? |
| --- | --- | --- | --- | --- |
| Pathway selected or changed | Yes | Yes | Yes | No |
| Evidence item added/edited/marked | No | No | No | No |

Evidence changes recompute coverage on read — they never invalidate plans by
themselves (a filled slot makes a planned module *redundant*, which the next
regular replan absorbs; auto-replan on evidence change is exactly the
autonomous-replanning the MVP excludes).

## 8. New reason codes (complete proposed list)

`PATHWAY_NOT_SELECTED`, `UNKNOWN_PATHWAY_ID`, `UNKNOWN_EVIDENCE_SLOT`,
`SLOT_MODULE_LIMIT_EXCEEDED`, `PATHWAY_REGISTRY_VERSION_MISMATCH` (selection
pinned to a version the registry no longer serves — surfaced, never silently
re-mapped). Intake-side failures reuse the existing generation codes
unchanged; theme/kind membership violations are repair-loop material like
weak spots, surfacing as `REPAIR_LIMIT_EXCEEDED` when persistent.
Knowledge-map codes are listed in `06-…`; the skill-grouping /
map-generation structured violations (`SKILL_GROUPING_MISSING_ENTRY`,
`SLOT_SEEDS_MISSING`, `KNOWLEDGE_MAP_BUDGET_EXCEEDED`) are
build/registry-time only and live in `07-tree-generation.md`.

## Spec-first checklist for NP-A (order matters)

1. `docs/axioms/00-product-thesis.md` — deterministic-ownership line above.
2. `docs/axioms/03-data-contracts.md` — register the two new specs.
3. `docs/specs/pathway-template.schema.md`, `pathway-selection.schema.md`,
   `skill-grouping.schema.md`, `knowledge-map-overlay.schema.md` (new; the
   last two per `07-tree-generation.md` / `06-…`, authored in KT-A);
   `user-profile.schema.md`,
   `resume-extraction.schema.md`, `strategy-constraints.schema.md`,
   `syllabus-units.schema.md` (amend).
4. Contracts + fixtures (valid + invalid with expected structured
   violations, per house pattern) + `make schemas`.
