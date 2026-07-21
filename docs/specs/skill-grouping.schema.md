# Skill Grouping Schema

## Owner

The deterministic knowledge-map generator (narrative-pathways KT-B; `tools/generate_knowledge_maps.py`).
KT-A authors the contract shape only.

## Consumers

The map generator (`07-tree-generation.md`), which reads a `SkillGrouping` plus a `PathwayTemplate`'s slot seeds to emit a `KnowledgeMap`; and the runtime add-node placement path (KT-C overlay), which reuses the same `skill_id → group` lookup to place a user-picked skill deterministically.

## Purpose

A `SkillGrouping` is a versioned overlay **beside** the skill taxonomy: it curates, **once per `skill_id`**, which group a skill belongs to, its per-skill honed-threshold prior (`expected_minutes`), and a display blurb.
Generation then reduces to membership lookup - the same `skill.rag` lands in the same group in every pathway map, so shared skills get identical placement without O(pathways) hand-drawing.
The shipped `skill-taxonomy` contract, its prompt slices, and its eval-recording pinning are untouched: this is a new, separately versioned artifact.

The honest split, stated once: **the method is deterministic; the knowledge stays curated.**
LLM/corpus research may *draft* grouping rows (the career-track-expansion profiles are the quarry, per the RI-F enrichment discipline); human review is the gate; the generator only ever arranges reviewed facts.

## JSON Example

```json
{
  "skill_grouping_version": "skill-grouping-v1",
  "taxonomy_version": "skill-taxonomy-v4",
  "groups": [
    {
      "group_id": "kg-retrieval",
      "title": "Retrieval & Grounding",
      "blurb": "Finding and feeding the right context to a model."
    }
  ],
  "entries": [
    {
      "skill_id": "skill.rag",
      "group_id": "kg-retrieval",
      "expected_minutes": 360,
      "blurb": "How dense and lexical retrieval differ, and when each wins."
    }
  ]
}
```

## Field Semantics

### `SkillGrouping`

| Field | Purpose |
| --- | --- |
| `skill_grouping_version` | Shape/content version; append-only file versions, taxonomy discipline. Stamped on the generated `KnowledgeMap` artifact so drift is reviewable |
| `taxonomy_version` | The pinned taxonomy the grouping was curated against; every entry's `skill_id` must resolve in it (registry-completeness test, KT-B) |
| `groups` | Non-empty list of `SkillGroup`s with unique `group_id`s |
| `entries` | Non-empty list of `SkillGroupingEntry`s with unique `skill_id`s; every entry's `group_id` must be declared in `groups` |

### `SkillGroup`

| Field | Purpose |
| --- | --- |
| `group_id` | Stable identifier, unique within the grouping; `^kg-[a-z0-9-]+$` |
| `title` | User-facing group name |
| `blurb` | 1-2 sentence display description; flows into the map group verbatim; prose, never parsed |

### `SkillGroupingEntry`

| Field | Purpose |
| --- | --- |
| `skill_id` | The skill this row places; unique within the grouping; resolves against the pinned taxonomy (registry test, KT-B) |
| `group_id` | The one group the skill belongs to - membership is a function, so cycles are structurally impossible. Must be declared in `groups` |
| `expected_minutes` | Per-skill prior for the honed threshold (`> 0`, heuristic prior like all durations); flows into the map node verbatim |
| `blurb` | 1-2 sentence display description; flows into the node verbatim; prose, never parsed |

## Contract vs. Registry / Generator Responsibility

The Pydantic contract (`backend/src/agentic_calendar/contracts/skill_grouping.py`) enforces only shape and internal consistency: field types and bounds, non-empty unique lists, unique `group_id`s and `skill_id`s, and that every entry's `group_id` is declared in `groups`.
The following live in KT-B (generator + registry tests), not in the contract:

- Every `skill_id` resolves against the pinned taxonomy version.
- **Demand-driven coverage**: the grouping has a row for every skill reachable from any registered pathway's slot seeds *and* for the whole add-picker slice of each live track. A seeded/pickable skill without a row fails generation with `SKILL_GROUPING_MISSING_ENTRY`, never a silently synthesized placement.
- No prestige terms in any text field (the extraction adapter's denylist, reused as a registry test).

## Invariants

- `groups` and `entries` are both non-empty.
- `group_id`s are unique within the grouping; `^kg-[a-z0-9-]+$`.
- `skill_id`s are unique within the grouping.
- Every entry's `group_id` is declared in `groups` (undeclared group is rejected at parse time).
- `expected_minutes >= 1`.
- The grouping is a deterministic literal; an LLM never produces one at runtime.

## Invalid Examples

```json
{
  "skill_grouping_version": "skill-grouping-v1",
  "taxonomy_version": "skill-taxonomy-v4",
  "groups": [{ "group_id": "kg-retrieval", "title": "Retrieval", "blurb": "b" }],
  "entries": [
    { "skill_id": "skill.rag", "group_id": "kg-not-declared", "expected_minutes": 360, "blurb": "b" }
  ]
}
```

Reason: entry `group_id` `kg-not-declared` is not declared in `groups`.

```json
{
  "entries": [
    { "skill_id": "skill.rag", "...": "..." },
    { "skill_id": "skill.rag", "...": "..." }
  ]
}
```

Reason: duplicate `skill_id` within the grouping.

```json
{
  "groups": [
    { "group_id": "kg-dup", "...": "..." },
    { "group_id": "kg-dup", "...": "..." }
  ]
}
```

Reason: duplicate `group_id` within the grouping.

## Structured Violations (build/registry-time only; KT-B)

`SKILL_GROUPING_MISSING_ENTRY`, `SLOT_SEEDS_MISSING`, `KNOWLEDGE_MAP_BUDGET_EXCEEDED` are emitted by the generator, never at runtime (`07-tree-generation.md`).
The reason codes are declared in KT-A with no producer.

## Related Docs

- `../axioms/00-product-thesis.md`
- `../axioms/03-data-contracts.md`
- `../axioms/08-rag-source-claims.md` (controlled-vocabulary wall)
- `skill-taxonomy.schema.md` (the artifact this versions beside)
- `pathway-template.schema.md` (`KnowledgeMap` output + `branch_skill_ids` slot seeds)
- `knowledge-map-overlay.schema.md`
- `../implementation-plans/narrative-pathways/07-tree-generation.md`
- `../implementation-plans/narrative-pathways/06-knowledge-tree.md`
