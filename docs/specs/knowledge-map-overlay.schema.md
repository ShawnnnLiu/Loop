# Knowledge Map Overlay Schema

## Owner

The per-account overlay store (narrative-pathways KT-B; append-only, disposition-store pattern).
KT-A authors the record shapes only.

## Consumers

The `narrative/` map-state kernel (KT-B `map_state`, which folds these records over the generated `KnowledgeMap` to compute per-node mastery tiers), the map API (KT-C: add-node, custom group/node CRUD, note upsert, set-point), and the map UI (KT-D).

## Purpose

An account's knowledge map = the generated `KnowledgeMap`(s) of its selected pathway(s) (`pathway-template.schema.md`) **plus** an append-only overlay of the seven record types below.
The overlay is how onboarding grants mastery, how a user adds skills we missed, how a user builds a personal layer (their own groups, nodes, notes) and adjusts their own mastery, and how a user deletes their own personal content (tombstones).
All seven records are `frozen`, deterministic, and never LLM-touched: no record carries model output, and no free-text field on any record ever enters a prompt.

Like everything in this folder: **curated knowledge, deterministic structure, LLM-free state.**

## Node and group identifiers

| Id | Pattern | Meaning |
| --- | --- | --- |
| generated node | `^kn-[a-z0-9-]+$` | a taxonomy-anchored skill node or a capstone in the generated map (`pathway-template.schema.md`) |
| generated group | `^kg-[a-z0-9-]+$` | a generated group |
| custom node | `^kcn-[a-z0-9-]+$` | a user-created personal node |
| custom group | `^kcg-[a-z0-9-]+$` | a user-created personal group |

"Any node" fields (`NodeNote.node_id`, `MasterySetPoint.node_id`) accept a generated (`kn-`) **or** custom (`kcn-`) node id.
`MasteryGrant.node_id` accepts **only** a generated (`kn-`) node id - grants are pathway content and have no meaning on personal nodes.

## The two content classes (normative)

- **Pathway content** - generated groups/nodes and taxonomy-anchored `NodeAddition`s. Counts toward branch counts, capstone/slot state, and fit; enters the Strategist vocabulary and the mastery slice.
- **Personal content** - `CustomGroup`s, `CustomNode`s, `NodeNote`s, and `CustomNode` names/descriptions. **Never counts toward pathway progress** - excluded from branch counts, capstone/slot state, fit, the coverage payload's pathway metrics, the Strategist vocabulary, and the mastery slice. Free text lives only here, and this class **never enters any prompt** - that is the injection wall, stated once.

## The add-only rule (normative)

> **Onboarding never subtracts.** Résumé intake, evidence confirmation, pathway selection, and pathway *change* may append `NodeAddition`s, `CustomGroup`s (never - onboarding is pathway content only), and `MasteryGrant`s - they may never remove a node, group, or note, or lower a tier.

Enforced structurally: the only records an onboarding/evidence code path may construct are `MasteryGrant` (`source: onboarding` / `evidence`) and taxonomy-anchored `NodeAddition`; the store is append-only, so "subtract" has no representation.
The only record that can ever lower mastery is a `MasterySetPoint` from the explicit per-node user control.
Deletion asymmetry: users may delete their **own** personal content via tombstone records (the disposition pattern, KT-C); pathway content is never deletable, only mastery-adjusted.

## Record Types

### `NodeAddition`

The user added a taxonomy skill we did not seed. Placement is deterministic: the added skill lands in the group its `skill-grouping` row names; code decides *where*, the user picks *what* from the closed add-picker vocabulary.

| Field | Purpose |
| --- | --- |
| `user_id` | Account owner |
| `skill_id` | The added taxonomy skill (closed vocabulary; the track's add-picker slice) |
| `created_at` | Timezone-aware instant |

Producer: the add-node API (KT-C). Rejections there: `SKILL_NOT_IN_TRACK_VOCABULARY`, `KNOWLEDGE_NODE_ALREADY_PRESENT`.

### `CustomGroup` (personal)

| Field | Purpose |
| --- | --- |
| `user_id` | Account owner |
| `custom_group_id` | `^kcg-[a-z0-9-]+$`, unique per account (store concern) |
| `name` | User-named cluster, `1..60` chars |
| `created_at` | Timezone-aware instant |

### `CustomNode` (personal)

| Field | Purpose |
| --- | --- |
| `user_id` | Account owner |
| `custom_node_id` | `^kcn-[a-z0-9-]+$`, unique per account (store concern) |
| `name` | `1..60` chars |
| `description` | Optional, `<= 500` chars |
| `group_id` | Any group the node sits in - a generated `kg-` group or a custom `kcg-` group |
| `created_at` | Timezone-aware instant |

Counts toward nothing: no branch counts, no fit, no capstones, no prompts. Trackable only by set-points; caps at `honed`.

### `NodeNote` (personal)

| Field | Purpose |
| --- | --- |
| `user_id` | Account owner |
| `node_id` | Any node (generated `kn-` or custom `kcn-`) |
| `text` | Free text, `1..2000` chars; display-only, private, never in any prompt or sponsor report |
| `created_at` / `updated_at` | Timezone-aware instants |

One note per node is a store-level cap (KT-C, `CUSTOM_CONTENT_LIMIT_EXCEEDED`).

### `MasteryGrant`

The only record type onboarding / evidence-confirm flows may write for mastery. Pathway content.

| Field | Purpose |
| --- | --- |
| `user_id` | Account owner |
| `node_id` | Taxonomy-anchored generated node only (`^kn-[a-z0-9-]+$`) |
| `credit_minutes` | Mastery-basis credit, `> 0` |
| `source` | `onboarding` or `evidence` |
| `created_at` | Timezone-aware instant |

### `MasterySetPoint`

The explicit per-node user control - the **only** record that can lower mastery. Set-points on custom nodes cap at `honed` (no `proven` without an evidence anchor).

| Field | Purpose |
| --- | --- |
| `user_id` | Account owner |
| `node_id` | Any node (generated `kn-` or custom `kcn-`) |
| `target_tier` | A `MasteryTier` (`discovered` / `training` / `honed` / `proven`) |
| `created_at` | Timezone-aware instant |

The mastery-basis fold over grants, set-points, and telemetry, and the tier ladder, are specified in `06-knowledge-tree.md` / `08-mastery-memory.md`; the kernel lands in KT-B.

### `PersonalContentTombstone` (personal)

The disposition-pattern delete for personal content (KT-C): an append-only "deleted" marker, since the store has no single-record delete. A user may delete only their **own** personal content - custom groups, custom nodes, and notes; pathway content (generated nodes, additions, grants) is never deletable, only mastery-adjusted.

| Field | Purpose |
| --- | --- |
| `user_id` | Account owner |
| `target_kind` | `PersonalContentKind`: `custom_group` / `custom_node` / `note` |
| `target_id` | The `kcg-` / `kcn-` id (group / node) or the note's `node_id` |
| `created_at` | Timezone-aware instant |

Read semantics (store/API, KT-C): a custom group / node with **any** tombstone for its id is deleted (ids are minted once, never reused). A node's note is deleted only when a `note` tombstone for that `node_id` is newer than the latest `NodeNote.updated_at` - so delete-then-re-add works. Deleting a node whose note exists tombstones nothing extra; the note is orphaned harmlessly (it renders on no node).

## Contract vs. Store Responsibility

The Pydantic contracts (`backend/src/agentic_calendar/contracts/knowledge_map_overlay.py`) enforce only shape and internal consistency: id patterns, field bounds and text-length caps, `credit_minutes > 0`, timezone-aware timestamps, and the taxonomy-anchored-only rule on `MasteryGrant.node_id`.
The following live in the store / API (KT-C), not in the contract:

- Per-account count caps (`<= 5` custom groups, `<= 20` custom nodes, one note per node) - heuristic priors, surfaced as `CUSTOM_CONTENT_LIMIT_EXCEEDED` with the specific bound in the structured violation detail.
- `custom_group_id` / `custom_node_id` per-account uniqueness.
- Add-picker vocabulary membership and duplicate-add rejection (`SKILL_NOT_IN_TRACK_VOCABULARY`, `KNOWLEDGE_NODE_ALREADY_PRESENT`).
- Module-tag validation against the account map (`UNKNOWN_KNOWLEDGE_NODE`, syllabus-units spec).

## Invariants

- Every record is `frozen` and forbids extra fields.
- Every timestamp is timezone-aware.
- `MasteryGrant.node_id` is a generated node id only; a custom (`kcn-`) id is rejected at parse time.
- `MasteryGrant.credit_minutes >= 1`.
- Text-length caps hold at parse time: `CustomGroup.name` and `CustomNode.name` `<= 60`; `CustomNode.description` `<= 500`; `NodeNote.text` `<= 2000`.

## Invalid Examples

```json
{ "user_id": "u1", "node_id": "kn-rag", "credit_minutes": -30, "source": "onboarding", "created_at": "2026-07-20T00:00:00+00:00" }
```

Reason: `credit_minutes` must be `> 0`.

```json
{ "user_id": "u1", "node_id": "kcn-my-thing", "credit_minutes": 60, "source": "onboarding", "created_at": "2026-07-20T00:00:00+00:00" }
```

Reason: `MasteryGrant.node_id` must be a generated (`kn-`) node; grants have no meaning on a custom node.

```json
{ "user_id": "u1", "node_id": "kn-rag", "text": "<2001 characters>", "created_at": "...", "updated_at": "..." }
```

Reason: `NodeNote.text` exceeds the `2000`-char cap.

## Structured Violations (runtime; KT-C)

`SKILL_NOT_IN_TRACK_VOCABULARY`, `KNOWLEDGE_NODE_ALREADY_PRESENT` (add-node API), `CUSTOM_CONTENT_LIMIT_EXCEEDED` (personal-content bound), `UNKNOWN_KNOWLEDGE_NODE` (module-tag validation, syllabus-units spec). The reason codes are declared in KT-A with no producer.

## Related Docs

- `../axioms/00-product-thesis.md`
- `../axioms/03-data-contracts.md`
- `../axioms/11-prerequisite-logic.md` (the non-interference wall the map obeys)
- `task-disposition.schema.md` (the append-only store pattern this copies)
- `pathway-template.schema.md` (the generated `KnowledgeMap` these records overlay)
- `skill-grouping.schema.md`
- `../implementation-plans/narrative-pathways/06-knowledge-tree.md`
- `../implementation-plans/narrative-pathways/08-mastery-memory.md`
