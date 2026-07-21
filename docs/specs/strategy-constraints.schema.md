# Strategy Constraints Schema

## Owner

The Strategist composition root (Phase 5b); part of the `StrategistInput` bundle.

## Consumers

`StrategistNode` (must respect these bounds when proposing a syllabus) and the
deterministic output gate in `llm_nodes/strategist.py` (which *disposes*:
rejects/repairs an out-of-bounds proposal).

## Purpose

The deterministic bounds a Strategist proposal must satisfy. The Strategist
*proposes* modules; these constraints are part of what the deterministic layer
uses to gate the output. All fields have spec defaults, so `{}` is valid.

## JSON Example

```json
{
  "max_modules": 12,
  "required_priority_values": ["high", "medium", "low"],
  "max_total_estimated_minutes": 4800,
  "must_reference_claims_for_company_specific_modules": true,
  "pathway_id": "ai-integration-engineer",
  "unfilled_slots": [
    {
      "slot_id": "public-artifact",
      "title": "Public writeup or talk",
      "gap_module_hint": "Write up one project as a technical narrative"
    }
  ],
  "max_slot_modules": 3,
  "knowledge_nodes": [
    { "node_id": "kn-rag", "title": "Retrieval fundamentals" },
    { "node_id": "kn-embeddings", "title": "Embeddings" }
  ],
  "mastered_node_ids": ["kn-rag"],
  "review_node_ids": ["kn-embeddings"],
  "max_review_modules": 2,
  "max_review_minutes": 60
}
```

## Field Semantics

| Field | Purpose |
| --- | --- |
| `max_modules` | Upper bound on syllabus module count (`> 0`, `<= 100`; default 12) |
| `required_priority_values` | Allowed `Priority` values, non-empty and unique (default `[high, medium, low]`) |
| `max_total_estimated_minutes` | Upper bound on summed module minutes (`> 0`; default 4800) |
| `must_reference_claims_for_company_specific_modules` | When true, a `company_specific` module must cite >= 1 `source_claim_id` (default true) |
| `pathway_id` | The selected pathway (default absent = no pathway shaping; narrative-pathways NP-A) |
| `unfilled_slots` | List of `{slot_id, title, gap_module_hint}` computed deterministically by the `narrative/` kernel from confirmed evidence - the Strategist is told the gaps, never asked to find them (default empty) |
| `max_slot_modules` | Upper bound on slot-linked modules per syllabus (`> 0`, `<= 10`; default 3; heuristic prior) |
| `knowledge_nodes` | The closed skill-node vocabulary the Strategist may tag modules against (`{node_id, title}`; narrative-pathways KT-C). The account's *pathway content* only - generated skill nodes plus taxonomy-anchored additions - projected by the composition root onto the account's knowledge map. `title` is a curated taxonomy display name, never user free text; personal custom content never appears here (the injection wall, `06-knowledge-tree.md`). A module tags the skills it trains via `SyllabusModule.knowledge_node_ids` (`syllabus-units.schema.md`), and the deterministic gate rejects any tag outside this vocabulary as `UNKNOWN_KNOWLEDGE_NODE`. Default empty (no selection = no map = today's bundle). |
| `mastered_node_ids` | The mastery slice (narrative-pathways MM-A). Node ids whose skills are *mastered* (tier >= `honed`) over the account map, computed deterministically by the kernel basis fold - generated nodes plus user additions. Advisory typed context, never a gate: the Strategist is told these are done and asked not to propose primary study whose training targets are all mastered. Must be a subset of `knowledge_nodes` (every id resolves to the account map). Default empty (no mastery data = today's behavior). |
| `review_node_ids` | Node ids whose skills are *review-flagged* - the raw minutes met the honed bar but the confidence-weighted basis did not (MM-A). Disjoint from `mastered_node_ids`; a subset of `knowledge_nodes`. The Strategist may propose at most `max_review_modules` short review modules for these. Default empty. |
| `max_review_modules` | Upper bound on all-mastered/review "review modules" per syllabus (`> 0`, `<= 10`; default 2; heuristic prior). Enforced by the MM-C deterministic gate (`REVIEW_MODULE_LIMIT_EXCEEDED`). |
| `max_review_minutes` | Per-module minutes cap for a review module (`> 0`; default 60; heuristic prior). Enforced by the MM-C deterministic gate (`MASTERY_REVIEW_BOUND_EXCEEDED`). |

The composition root fills the pathway fields from the profile's
`pathway_selection` (NP-D), the knowledge vocabulary from the account's
knowledge map plus overlay additions (KT-C), and the mastery slice by
projecting the skill-keyed basis fold onto the same account map (MM-C); a
profile without a selection produces the defaults, and the constraint bundle
is byte-identical to today's. The mastery slice is advisory typed context
that shapes what the Strategist is *asked to propose* - it never gates
unlocks, task availability, scheduling, or any user action (the
`06-knowledge-tree.md` non-interference rule, amended only in this forward
direction by `08-mastery-memory.md`).

## Invariants

- `required_priority_values` is non-empty and contains no duplicates.
- `max_modules` in `(0, 100]`; `max_total_estimated_minutes > 0`.
- `max_slot_modules` in `(0, 10]`.
- `unfilled_slots` requires `pathway_id`: a non-empty gap list with no
  selected pathway is contradictory and rejected.
- `unfilled_slots[].slot_id` values are unique.
- `knowledge_nodes` requires `pathway_id`: a vocabulary with no selected
  pathway is contradictory and rejected (a map requires a selection).
- `knowledge_nodes[].node_id` values are unique and match `^kn-[a-z0-9-]+$`.
- `mastered_node_ids` and `review_node_ids` require `pathway_id`: mastery data
  exists only for a selected pathway.
- `mastered_node_ids` and `review_node_ids` each contain unique ids matching
  `^kn-[a-z0-9-]+$`, and the two lists are disjoint (a node is either done or
  flagged for review, never both).
- Every id in `mastered_node_ids` and `review_node_ids` must appear in
  `knowledge_nodes` (each mastery id resolves to the account map - the
  composition-time guarantee backed by this contract invariant).
- `max_review_modules` in `(0, 10]`; `max_review_minutes > 0`.
- Unknown fields are rejected (`extra="forbid"`).

## Invalid Examples

```json
{ "required_priority_values": [] }
```

Reason: `required_priority_values` must be non-empty.

```json
{ "required_priority_values": ["high", "high"] }
```

Reason: duplicate priority values.

```json
{
  "unfilled_slots": [
    { "slot_id": "public-artifact", "title": "Public writeup or talk", "gap_module_hint": "Write it up" }
  ]
}
```

Reason: `unfilled_slots` without `pathway_id`.

```json
{
  "knowledge_nodes": [{ "node_id": "kn-rag", "title": "Retrieval fundamentals" }]
}
```

Reason: `knowledge_nodes` without `pathway_id`.

```json
{
  "pathway_id": "ai-integration-engineer",
  "knowledge_nodes": [{ "node_id": "kn-rag", "title": "Retrieval fundamentals" }],
  "mastered_node_ids": ["kn-rag"],
  "review_node_ids": ["kn-rag"]
}
```

Reason: `mastered_node_ids` and `review_node_ids` overlap (`kn-rag`).

```json
{
  "pathway_id": "ai-integration-engineer",
  "knowledge_nodes": [{ "node_id": "kn-rag", "title": "Retrieval fundamentals" }],
  "mastered_node_ids": ["kn-embeddings"]
}
```

Reason: `mastered_node_ids` references a node absent from `knowledge_nodes`.

```json
{ "mastered_node_ids": ["kn-rag"] }
```

Reason: mastery slice without `pathway_id`.

## Related Docs

- `syllabus-units.schema.md` ("Strategist Inputs")
- `strategist-input.schema.md`
- `pathway-template.schema.md`
- `pathway-selection.schema.md`
- `../axioms/04-validation-layer.md`
