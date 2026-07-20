# 06 · Knowledge Map — Groups, Per-Account Ownership, Customization

First written 2026-07-16 as "Knowledge Tree"; **reworked 2026-07-19**
(filename kept so links stay stable). Same status as the rest of the
folder: **planning only, nothing implemented.** This doc extends `02-…`
(registry/contracts) and `04-…` (increments); generation mechanics live in
`07-tree-generation.md`; mastery mechanics live in `08-mastery-memory.md`.

Two structural changes from the first draft:

1. **Groups, not a DAG.** The map is no longer a prerequisite-edge tree.
   It is a two-level grouping: branches (one per evidence slot) contain
   **group nodes** — clickable clusters that expand into their member
   **skill nodes**. No edges, no depth computation, no cycles, no
   transitive reduction; generation (`07-…`) reduces to membership lookup.
2. **Per-account, add-only from onboarding, user-customizable.** The map
   belongs to the account, not to a pathway selection. Onboarding and
   pathway changes only ever **add** to it. Users can add nodes we missed
   (from the career vocabulary), create and name their **own groups and
   nodes**, attach descriptions and private notes to any node, and adjust
   per-skill mastery — including **down**. An explicit per-node user
   action is the only thing that ever lowers anything. User-created
   content is a **personal layer**: it never counts toward pathway
   progress and never enters any prompt.

Like everything in this folder: **curated knowledge, deterministic
structure, LLM-free state.** Group membership is curated once per skill;
the user's per-node tier is a pure function of stored records; no LLM
assigns, names, or explains a mastery tier numerically.

## The non-interference rule (normative, unchanged in spirit)

The map is a *presentation and memory layer*. Its groups suggest how
knowledge clusters; they never gate the Planner, the Scheduler, or task
availability. Axiom-11 prerequisite computation over task dependencies
remains the only unlock system in the control plane. One narrow, explicitly
typed exception is specified in `08-mastery-memory.md`: deterministically
computed mastery may enter `StrategyConstraints` as advisory generation
context (the `unfilled_slots` mechanism) — shaping what the Strategist
*proposes*, never what the user or scheduler *may do*.

## Contract — two layers

### Layer 1 — generated `KnowledgeMap` (registry artifact, per pathway)

Amendment to `pathway-template.schema.md` (KT-A). Emitted by the
deterministic generator (`07-…`), never hand-authored:

```json
{
  "knowledge_map": {
    "groups": [
      {
        "group_id": "kg-retrieval",
        "title": "Retrieval & Grounding",
        "branch": "llm-feature-depth",
        "blurb": "Finding and feeding the right context to a model.",
        "member_node_ids": ["kn-rag", "kn-embeddings"]
      }
    ],
    "nodes": [
      {
        "node_id": "kn-rag",
        "title": "Retrieval fundamentals",
        "kind": "skill",
        "skill_id": "skill.rag",
        "group_id": "kg-retrieval",
        "expected_minutes": 360,
        "blurb": "How dense and lexical retrieval differ, and when each wins."
      },
      {
        "node_id": "kn-llm-feature-capstone",
        "title": "LLM feature shipped",
        "kind": "capstone",
        "evidence_slot_id": "llm-feature-depth",
        "branch": "llm-feature-depth"
      }
    ]
  }
}
```

| Field | Semantics |
| --- | --- |
| `group_id` | unique within the map, `^kg-[a-z0-9-]+$` |
| `branch` (on group) | the evidence `slot_id` the group serves, or `core` (serves 2+ slots) |
| `member_node_ids` | the group's skill nodes; non-empty |
| `node_id` | unique within the map, `^kn-[a-z0-9-]+$` |
| `kind` | `skill` (taxonomy-anchored, lives in exactly one group) · `capstone` (one per evidence slot, branch-level, no group) |
| `skill_id` | taxonomy anchor; required for `kind: skill` |
| `expected_minutes` | prior for the honed threshold (`> 0`; heuristic prior like all durations) |
| `blurb` | 1–2 sentence display description; prose, never parsed |

Invariants (contract + registry tests, invalid fixtures for each): unique
ids; every skill node in exactly one group and every `member_node_ids`
entry resolving both ways; groups non-empty; exactly one capstone per
evidence slot and none dangling; `skill_id`s resolve against the pinned
taxonomy version; prestige denylist over all text fields (shared constant).
There are **no edges** — cycle handling is deleted, not deferred.

### Layer 2 — per-account overlay (new spec `knowledge-map-overlay.schema.md`)

The account's map = the generated map(s) of its selected pathway(s) plus an
append-only overlay store (house pattern: `TaskDispositionRecord`). Six
record types, all `frozen`, all deterministic, none LLM-touched:

| Record | Fields (sketch) | Producer |
| --- | --- | --- |
| `NodeAddition` | `user_id`, `skill_id`, `added_at` | explicit user action ("Add a skill" — taxonomy picker) |
| `CustomGroup` | `user_id`, `custom_group_id`, `name` (≤ 60 chars), `created_at` | explicit user action ("New group") |
| `CustomNode` | `user_id`, `custom_node_id`, `name` (≤ 60 chars), `description` (≤ 500 chars, optional), `group_id` (any group — curated or custom), `created_at` | explicit user action ("New node") |
| `NodeNote` | `user_id`, `node_id` (any node, incl. custom), `text` (≤ 2000 chars), timestamps | explicit user action |
| `MasteryGrant` | `user_id`, `node_id` (taxonomy-anchored only), `credit_minutes` (> 0), `source` (`onboarding` · `evidence`), `created_at` | onboarding / evidence confirm flows — **the only records onboarding may write** |
| `MasterySetPoint` | `user_id`, `node_id` (any node, incl. custom), `target_tier`, `created_at` | explicit per-node user action — **the only record that can lower mastery** |

`NodeAddition` placement is deterministic: the added skill lands in the
group its `skill-grouping` row names (`07-…`); if that group isn't on the
account's map yet, the group is added with the one member. The user picks
*what* from a closed list; code decides *where*. `CustomGroup` /
`CustomNode` placement is the user's — it is their personal layer, so
free-form is fine there and only there.

**The two content classes (normative):**

- **Pathway content** — generated groups/nodes and taxonomy-anchored
  `NodeAddition`s. Counts toward branch counts, capstone/slot state, and
  fit; enters the Strategist vocabulary and the mastery slice (`08-…`).
- **Personal content** — `CustomGroup`s, `CustomNode`s, `NodeNote`s, and
  `CustomNode` names/descriptions. **Never counts toward pathway
  progress** — excluded from branch counts, capstone/slot state, fit, the
  coverage payload's pathway metrics, the Strategist vocabulary, and the
  mastery slice. Free text lives only here, and this class **never enters
  any prompt** — that is the injection wall, stated once.

Deletion asymmetry: users may delete their **own** personal content
(append-only store, tombstone records — the disposition pattern); pathway
content is never deletable, only mastery-adjusted. Onboarding deletes
nothing of either class.

## The add-only rule (normative)

> **Onboarding never subtracts.** Résumé intake, evidence confirmation,
> pathway selection, and pathway *change* may append nodes, groups, and
> `MasteryGrant`s — they may never remove a node, group, or note, or
> lower a tier. Changing pathway adds the new pathway's groups and touches
> nothing else; nodes no longer served by any selected pathway remain on
> the map (they are the user's history). The only way any mastery goes
> down is a `MasterySetPoint` from the explicit per-node control.

Enforced structurally, not by convention: the onboarding code paths can
only construct grant/addition records (KT-A contract), and the overlay
store is append-only, so "subtract" has no representation.

## Mastery tiers — deterministic ladder, four states

The DAG's `locked` state is gone with the edges (this resolves old open
decision d3 — there is nothing to lock behind). Proposed names (d1):

| Tier | Meaning | Computed from |
| --- | --- | --- |
| `discovered` | on the map, no work yet | zero mastery basis |
| `training` | work underway | ≥ 1 linked task in the active plan, or basis > 0 but below the honed bar |
| `honed` | the study happened (or the user says they own it) | mastery basis ≥ `honed_fraction × expected_minutes` (prior `0.8`, `tuning.toml`) |
| `proven` | backed by a real artifact | `honed` **and** — capstone: its evidence slot is `filled`; skill: a confirmed evidence item carries a matching anchor. Always user-gated via "mark evidence"; never automatic |

**Mastery basis** is a deterministic fold over the account's records —
telemetry accumulation + grants + set-points — specified once in
`08-mastery-memory.md` so kernel and tests can't drift. "Check off" on a
node is simply a `MasterySetPoint` to `honed`; "I'm rusty" is a set-point
to a lower tier. Group nodes have no tier of their own: collapsed, a group
shows honest member counts ("2/5 honed"), never an average or score.

**Custom nodes** (personal layer) carry a simpler state: set-points are
their *only* mastery source — no `expected_minutes`, no telemetry linkage
(modules can't tag them; they're not in the vocabulary), no grants. They
climb `discovered → training → honed` purely by the user's own check-off
and cap at `honed` — `proven` requires an evidence anchor custom nodes
don't have (d7 revisits). Their state colors the map but joins no count.

What is deliberately **not** here: XP, levels, percentile ranks, decay
timers, and any LLM judgment of quality. "Honed" claims the work happened
*or the user explicitly claimed it* (the set-point is visible in the node
drawer as "self-assessed" — honest labeling); "proven" claims an artifact
exists. The system never certifies competence it can't observe.

## Plumbing — how modules light nodes

`syllabus-units.schema.md` (KT-A): `SyllabusModule` gains optional
`knowledge_node_ids` (max 3), mirroring `source_claim_ids` mechanics:

- The Strategist prompt (when a pathway is selected) embeds **the
  account's pathway content** — generated nodes *plus taxonomy-anchored
  additions*, never personal content — as a closed vocabulary of node ids
  + titles (all taxonomy display names, never user free text; same budget
  discipline as the weak-spot slice) and tags each proposed module with
  the nodes it trains. A vocabulary-added node is thereby a first-class
  planning target: add "missed" skills and the next generation studies
  them. Custom nodes and all names/descriptions/notes stay out of every
  prompt, categorically.
- Deterministic gate: unknown id → `UNKNOWN_KNOWLEDGE_NODE` (checked
  against the account map); more than 3 → contract bound. Untagged modules
  are valid — general modules exist.
- Tasks inherit via their existing `module_id` (task-plan contract
  untouched; Planner and Scheduler never see the map).

Kernel (KT-B): `narrative/` gains
`map_state(account_map, overlay_records, plan, telemetry) → {node_id: tier}`
— a pure function; the API computes it on read. The overlay store is the
one new store (append-only, disposition-store pattern).

Runtime reason codes: `UNKNOWN_KNOWLEDGE_NODE` (validation of module
tags); `SKILL_NOT_IN_TRACK_VOCABULARY` and
`KNOWLEDGE_NODE_ALREADY_PRESENT` (add-node API);
`CUSTOM_CONTENT_LIMIT_EXCEEDED` (any personal-content bound — counts or
text lengths — with the specific bound in the structured violation
detail; caps are heuristic priors: ≤ 5 custom groups, ≤ 20 custom nodes,
one note per node). Generation-time structured violations live in `07-…`
and can never occur at runtime.

## Customization surfaces (the complete list)

1. **Add a skill** (pathway content) — search picker over the account's
   career-track taxonomy slice, minus nodes already present. Closed
   vocabulary from our database; these are the additions that become
   plannable and feed mastery memory. Typed rejections above.
2. **Create a group** (personal) — user-named cluster (≤ 60 chars),
   placed on the map beside the pathway branches. Holds custom nodes;
   curated nodes stay in their generated groups.
3. **Create a node** (personal) — user-named (≤ 60 chars), optional
   description (≤ 500 chars), placed in any group, curated or custom.
   Trackable by check-off/set-points; **counts toward nothing** — no
   branch counts, no fit, no capstones, no prompts. This is where "skills
   the vocabulary doesn't have" live without breaking the axiom-08 wall:
   the taxonomy still grows only by curation, and a recurring custom node
   across users is a *signal to curate*, not an automatic entry.
4. **Notes on any node** — one free-text note per node (≤ 2000 chars),
   curated or custom: the user's own framing, resources, reminders.
   Display-only and private: never enters any prompt, never
   control-plane, never in sponsor reports, no mastery effect.
5. **Adjust mastery** — the per-node set-point control, up or down.
   Down-adjusting a pathway node drops it out of the mastered set, so the
   next generation offers it for study again (`08-…`) — that is the
   feature, not a side effect. On custom nodes the same control is pure
   personal tracking.
6. **Mark evidence** — unchanged from `01-…`/`02-…`; the only path to
   `proven` (pathway nodes only).

## UI — the Knowledge Map (expandable groups in Loop's skin)

Loop's design language is warm paper, ink, clay, sage, gold
(`frontend/src/styles/tokens.css`) — an **illuminated cartographer's
chart**, not a neon tech-tree. The interaction model replaces the fixed
DAG chart:

- **Collapsed view (default):** branches fan from the spine header (one
  per evidence slot, capstone shield at the head); each branch shows its
  **group waypoints** — larger circles with the group title and an honest
  count chip ("Retrieval & Grounding · 2/5 honed"). ≤ ~8 groups per
  pathway renders trivially on one screen.
- **Click a group → it expands in place** into its member skill nodes
  (inline accordion on mobile, radial bloom on desktop — d5); click again
  collapses. Multiple groups may be open; state is client-side only.
- **Node states** (the gilding ramp, unchanged): `discovered` = white
  fill, `--muted` outline; `training` = `--clay-tint` fill, `--clay` ring
  with a soft pulse; `honed` = `--gold-soft` fill, `--gold` ring; `proven`
  = solid `--gold` fill, `--gold-deep` ring. A group waypoint fills
  proportionally by member count (paper → gold), with no percentage text.
  Self-assessed honed nodes carry a small "self-assessed" tick in the
  drawer, not on the map (no shaming badges).
- **Click a node → detail drawer** (mobile: bottom sheet): blurb, taxonomy
  chips, linked modules/tasks with live status, attached evidence, the
  personal note (inline editor), the adjust-mastery control, and "mark
  evidence" on honed pathway nodes. Custom-node drawers show
  name/description editors instead of taxonomy chips.
- **Personal layer rendering:** custom groups sit after the pathway
  branches under a quiet "Your additions" header; custom nodes (wherever
  placed) render with an ink outline instead of the branch's gold ramp
  base, so the pathway story and the personal layer read as one map
  without lying about what counts. Header-strip and group-chip counts
  cover pathway content only.
- **Create/add affordances:** "Add a skill" (picker) at map level and
  inside each expanded group; "New group" at map level; "New node" inside
  any expanded group. Personal content is editable and deletable in
  place; pathway content is not.
- **Header strip:** per-branch counts only — "LLM feature depth · 3/5
  honed · capstone unproven". No XP bars, no levels, no percentages.
- **Motion:** one brief fill animation on tier change while the view is
  open; expand/collapse respects `prefers-reduced-motion`; nothing loops
  except the training pulse, which also stills under reduced motion.
- **Empty states:** no pathway → faded map illustration + CTA into the
  Your-story step; fresh selection → all discovered with the copy "Your
  map is charted. Time to walk it."
- Placement: Progress screen — Story panel stays the compact summary,
  "View knowledge map" expands to the full chart.

**Visual source of truth:** `docs/design-reference/Loop - Pathway Map.html`
is the hi-fi page for the *original DAG design* — its tier ramp, drawer,
and empty states carry over; its edge/lineage rendering and fixed layout do
**not**. The canvas needs a re-pass for the group-expansion interaction
before KT-D; until then this doc is normative for semantics *and* layout,
and the design page for palette/components only. Copy that survives:
"Study lights a branch from the roots; proof crowns it."

## Increments — KT-A … KT-D (one commit each, house gates)

Sequenced against `04-…`: KT-A/KT-B need NP-B's registry; KT-C needs
NP-D's strategist plumbing; KT-D needs NP-E's screens. Run the KT series
after NP-F, or interleave at those seams.

- **KT-A — contracts.** Spec amendments (`pathway-template`,
  `syllabus-units`), the new `skill-grouping.schema.md` (`07-…`) and
  `knowledge-map-overlay.schema.md` (six record types above, add-only
  producer constraints and the pathway/personal content-class split
  stated normatively), reason codes, Pydantic + fixtures (incl.
  empty-group, dangling-capstone, multi-group-membership,
  grouping-missing-entry, over-cap custom content, negative-grant,
  grant-on-custom-node invalids), `make schemas`.
- **KT-B — grouping overlay + generator + kernel.** Curated
  `skill_grouping_v1.json` rows for every skill reachable from the seed
  pathways' slot seeds (content quarry: the career-track-expansion skill
  lists), the `tools/` generator + `make maps` / `maps-check` per `07-…`,
  the committed map artifact, the overlay store (append-only, SQLite,
  parametrized shared suite), `map_state` + the mastery fold in
  `narrative/` (grants + set-points; confidence weighting arrives with
  MM-B), `honed_fraction` prior in `tuning.toml` + threshold-change-log
  entry, exhaustive tier tests (each transition, fold ordering,
  set-point-rebase, grant accumulation, add-only property) + generator
  determinism tests (byte-identical re-run, tie-break fixtures).
- **KT-C — strategist + API.** Prompt vocabulary from the account's
  pathway content + output gate; API surfaces: add-node (picker), custom
  group/node CRUD (bounded, tombstone deletes), note upsert, set-point,
  all with typed rejections; a personal-content-exclusion test (custom
  names/notes appear in no prompt bundle, no coverage metric, no sponsor
  payload); composition-root wiring; `map` block in the coverage payload;
  validation tests per reason code.
- **KT-D — the map UI.** Group expand/collapse renderer + drawer + picker
  + create-group/create-node flows + note editor + adjust-mastery control
  + vitest; design-canvas re-pass first (see visual source of truth
  note); CDP smoke: select pathway → approve plan → complete a task →
  node flips to `training`/`honed`; add a vocabulary node → tag it in a
  regenerated plan; create a custom group/node + note → visible, counts
  unchanged; set-point down → node leaves the mastered set — all in a
  real browser. Every tier on screen must be reproducible by calling
  `map_state` on stored data.

## Tandem note

Mechanics carry unchanged; only content shifts: coursework and
activity-shaped groups, multi-year branches, capstones = application
pillars. Grouping absorbs scale better than the DAG did — 60 nodes is ~12
collapsed waypoints. The counselor/sponsor surface may show **branch
counts only** (never node detail, never notes or custom content) under
existing permission tiers — the map itself stays user-private.

## Open decisions (adds to the README list)

- **d1 · Tier names**: `Discovered / Training / Honed / Proven` proposed —
  four states now; `locked` is resolved-by-removal (no edges to lock
  behind).
- **d2 · Honed basis**: minutes-fraction (proposed, telemetry-native) vs
  all-linked-modules-complete. Prior 0.8 either way, tunable. `08-…`
  extends the minutes term with confidence weighting (its m1) and the
  grant/set-point fold.
- **d4 · Map size**: 20–40 skill nodes per Loop pathway (Tandem ceiling
  60), ~4–8 skills per group as the grouping guideline — enforced by the
  generator as a loud failure, never silent pruning (`07-…`).
- **d5 · Group expansion interaction**: inline accordion everywhere
  (simpler, one code path) vs radial bloom on desktop (prettier). Design
  decision for the canvas re-pass; semantics identical.
- **d6 · Map without a selection**: v1 requires a pathway selection to
  instantiate the map (additions ride it; NP skip-path guarantee stays
  byte-identical). A selection-free "just track my skills" map is real but
  deferred.
- **d7 · Evidence on custom nodes**: custom nodes cap at `honed` in v1
  (no anchor for "mark evidence"). Letting users attach evidence to
  personal nodes is plausible but drags free text toward the evidence
  kernel — revisit after dogfood.
- **Grant sizing** is `08-…`'s m6; **generation decisions** are `07-…`'s
  g-series.
