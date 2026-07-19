# 06 · Knowledge Tree — The Map of a Pathway

Added 2026-07-16, same status as the rest of the folder: **planning only,
nothing implemented.** This doc extends `02-…` (registry/contracts) and
`04-…` (increments) with the per-pathway knowledge tree: a DAG of
knowledge nodes with deterministic mastery tiers, rendered as an RPG-style
progression map. The DAG itself is not hand-drawn — it is generated
deterministically from a curated skill graph (`07-tree-generation.md`). It is the visual centerpiece of the story layer — the
screen a user opens to *feel* their progress.

## What the tree is (and the one rule that keeps it safe)

Each `PathwayTemplate` carries one **knowledge tree**: 20–40 nodes
arranged in branches, one branch per evidence slot ("constellation" =
pillar), each branch crowned by a **capstone node that IS the slot**. Study
progress lights a branch from the roots; a confirmed artifact ("mark
evidence") crowns it. One surface tells the whole story: what you know, what
you're training, what you've proven.

**The non-interference rule (normative):** the tree is a *presentation
layer*. Its prerequisite edges suggest a learning order visually; they never
gate the Planner, the Scheduler, or task availability. Axiom-11 prerequisite
computation over task dependencies remains the only unlock system in the
control plane. A "locked" tree node is a rendering state, not a permission —
if the Strategist schedules work on it anyway, it simply lights up. This is
what keeps the tree from becoming a second, competing prerequisite engine.

Like everything in this folder: **curated knowledge, deterministic
structure, LLM-free rendering.** The tree shape is generated registry
content — a pure function (`07-…`) over the curated skill graph and each
slot's seed skills, committed and human-reviewed as concrete diffs; the
user's per-node tier is a pure function of confirmed data; no LLM assigns,
names, or explains a mastery tier numerically.

## Contract — `KnowledgeTree` inside `PathwayTemplate`

Amendment to `pathway-template.schema.md` (KT-A):

```json
{
  "knowledge_tree": {
    "nodes": [
      {
        "node_id": "kn-retrieval-basics",
        "title": "Retrieval fundamentals",
        "kind": "skill",
        "skill_id": "skill.rag",
        "branch": "llm-feature-depth",
        "depth": 1,
        "expected_minutes": 360,
        "blurb": "How dense and lexical retrieval differ, and when each wins."
      },
      {
        "node_id": "kn-llm-feature-capstone",
        "title": "LLM feature shipped",
        "kind": "capstone",
        "evidence_slot_id": "llm-feature-depth",
        "branch": "llm-feature-depth",
        "depth": 3
      }
    ],
    "edges": [
      { "from": "kn-retrieval-basics", "to": "kn-llm-feature-capstone" }
    ]
  }
}
```

| Field | Semantics |
| --- | --- |
| `node_id` | unique within the tree, `^kn-[a-z0-9-]+$` |
| `kind` | `skill` (taxonomy-anchored) · `concept` (knowledge without a taxonomy row) · `capstone` (one per evidence slot, exactly) |
| `skill_id` | optional anchor into the skill taxonomy — reuses display names/aliases; required for `kind: skill` |
| `evidence_slot_id` | required iff `kind: capstone`; must reference a slot of the same template |
| `branch` | the evidence `slot_id` the node belongs to, or `core` (shared trunk) |
| `depth` | layout row within the branch (`0` = trunk-adjacent); rendering derives positions from `(branch, depth, index)` — no hand-placed coordinates |
| `expected_minutes` | prior for the honed threshold (`> 0`; heuristic prior like all durations) |
| `blurb` | 1–2 sentence display description; prose, never parsed |

Invariants (contract + registry tests, invalid fixtures for each):

- Edges form a **DAG** — cycle → structured violation `KNOWLEDGE_TREE_CYCLE`.
- Edge endpoints exist; `node_id`s unique; exactly one capstone per
  evidence slot and none dangling.
- `skill_id`s resolve against the pinned taxonomy version
  (registry-completeness test, same pattern as theme membership).
- Every non-capstone node reaches at least one capstone (no orphan
  islands — guarantees every node visibly serves a pillar).
- Prestige denylist over all text fields (shared constant).

The tree literal is emitted by the deterministic generator
(`07-tree-generation.md`), never hand-authored per pathway. The invariants
above double as the generator's acceptance tests — the invalid fixtures
stay, because the contract must reject a bad tree no matter who produced
it.

## Mastery tiers — deterministic ladder, five states

Proposed names (open decision d1 — flavor without dishonesty):

| Tier | Meaning | Computed from |
| --- | --- | --- |
| `locked` | prerequisites untouched | display-only: node has prereq edges and none of its prereq nodes is ≥ `honed`, and no work of its own exists |
| `discovered` | reachable, no work yet | prereqs ≥ `honed` (or no prereqs), zero linked work |
| `training` | work scheduled or partially done | ≥ 1 linked task in the active plan or ≥ 1 completed linked task, below the honed bar |
| `honed` | the planned study is done | completed minutes on linked tasks ≥ `honed_fraction × expected_minutes` (prior `0.8`, lives in `tuning.toml` beside the scheduler weights) |
| `proven` | backed by a real artifact | `honed` **and** — capstone: its evidence slot is `filled`; skill/concept: a confirmed evidence item carries a matching `theme_tag`/`skill_id` anchor. Always user-gated via "mark evidence"; never automatic |

Precedence is upward-only per state computation (`proven > honed > training >
discovered > locked`); any linked work promotes a node out of `locked`
regardless of prereqs (non-interference made visible). Completed minutes use
telemetry `actual` durations where recorded, planned minutes otherwise —
stated once here so kernel and tests can't drift.

What is deliberately **not** here: XP, levels, percentile ranks, decay
timers, and any LLM judgment of quality. "Honed" claims the *work happened*
(telemetry fact); "proven" claims an *artifact exists* (user-confirmed
fact). The system never certifies competence it can't observe.

## Plumbing — how modules light nodes

`syllabus-units.schema.md` (KT-A): `SyllabusModule` gains optional
`knowledge_node_ids` (max 3), mirroring `source_claim_ids` mechanics
exactly:

- The Strategist prompt (when a pathway is selected) embeds the tree's
  node ids + titles as a closed vocabulary (~40 short strings, +400–700
  input tokens — same budget discipline as the weak-spot slice) and tags
  each proposed module with the nodes it trains.
- Deterministic gate: unknown id → `UNKNOWN_KNOWLEDGE_NODE`; more than 3 →
  contract bound. Untagged modules are valid — general modules exist.
- Tasks inherit via their existing `module_id` (task-plan contract
  untouched; Planner and Scheduler never see the tree).

Kernel (KT-B): `narrative/` gains
`tree_state(profile, plan, telemetry, template) → {node_id: tier}` — a pure
function; the API computes it on read (NP-D's coverage payload grows a
`tree` block when a selection exists). No new store, no background jobs.

New reason codes: `UNKNOWN_KNOWLEDGE_NODE` (validation),
`KNOWLEDGE_TREE_CYCLE` (contract/registry structured violation). That's the
complete runtime list — display states are not failures. The
generation-time structured violations (`SKILL_GRAPH_CYCLE` and friends)
live in `07-…` and can never occur at runtime.

## UI — the Knowledge Map (RPG structure in Loop's skin)

Loop's design language is warm paper, ink, clay, sage, gold
(`frontend/src/styles/tokens.css`) — so the map is an **illuminated
cartographer's chart**, not a neon tech-tree: constellation branches
ink-drawn on paper, nodes as waypoints that fill with the brand colors as
tiers rise. Distinctive, on-brand, and it ages better than sci-fi chrome.

Layout (deterministic, hand-rolled SVG, **no new dependencies**):

```
                        ◈ AI-Integration Engineer          ← spine header
                        │
          ┌─────────────┼──────────────┐
     LLM feature     Integration    Public artifact        ← branches =
       depth           breadth         (writing)              evidence slots
          │              │                │
        (kn)───(kn)    (kn)──(kn)       (kn)                ← depth 0..n
          │      \       │                │
        (kn)     (kn)  (kn)             (kn)
          └──────┬┘      │                │
              ⛊ capstone ⛊ capstone     ⛊ capstone          ← the pillars
```

- Branches fan from a spine header; positions derive from
  `(branch, depth, index)` — column per branch, row per depth. ≤ 40 nodes
  renders trivially; pan/scroll horizontally on narrow screens (the Week
  board precedent), vertical stack under 720px.
- **Node states** (the design's "gilding ramp" — paper to gold as tiers
  rise): `locked` = `--paper-2` fill, dashed `--line-3` outline, muted
  title; `discovered` = white fill, `--muted` outline; `training` =
  `--clay-tint` fill, `--clay` ring with a soft pulse; `honed` =
  `--gold-soft` fill, `--gold` ring; `proven` = solid `--gold` fill,
  `--gold-deep` ring. Capstones are larger, shield-shaped, with a
  "CAPSTONE — UNPROVEN" / "PROVEN" banner.
- **Edge states:** `--line-2` default; ink once the downstream node is ≥
  `training`; gold when both ends are `proven`.
- **Hover** highlights the ancestor path to the trunk (the RPG skill-tree
  convention that teaches structure without words). **Click** opens a
  detail drawer: blurb, taxonomy chips, linked modules/tasks with live
  status, attached evidence, and for locked nodes the prereq list ("Charted
  after: Retrieval fundamentals") — plus a "mark evidence" shortcut on
  honed nodes.
- **Header strip:** per-branch counts only — "LLM feature depth · 3/5
  honed · capstone unproven". No XP bars, no levels, no percentages
  (consistent with slot-counts-not-scores).
- **Motion:** one brief fill animation when a node changes tier while the
  view is open (client detects state diff); `prefers-reduced-motion`
  honored; nothing loops except the training pulse, which also stills under
  reduced motion.
- **Empty states:** no pathway → the panel shows a faded map illustration
  and a CTA into the Your-story step; fresh selection → all
  discovered/locked with the copy "Your map is charted. Time to walk it."
- Placement: Progress screen — the Story panel's pillars (from `01-…`) and
  the map are the same data at two zoom levels; Story stays the compact
  summary, "View knowledge map" expands to the full chart.

**Visual source of truth:** `docs/design-reference/Loop - Pathway Map.html`
(the design canvas calls this feature "Pathway Map" — same thing). It is a
self-contained hi-fi page with desktop 1240 + mobile 396 frames, all five
tier states, hover lineage ("trace a node to the roots"), the detail drawer
(mobile: bottom sheet), and both empty states. Division of authority: this
doc is normative for semantics and mechanics (tier computation,
non-interference, honest counts); the design page is normative for visuals
and layout. Copy that survives from the design: "Study lights a branch from
the roots; proof crowns it."

## Increments — KT-A … KT-D (one commit each, house gates)

Sequenced against `04-…`: KT-A/KT-B need NP-B's registry (trees live inside
pathway templates); KT-C needs NP-D's strategist plumbing; KT-D needs NP-E's
screens. Run the KT series after NP-F, or interleave at those seams.

- **KT-A — contracts.** Spec amendments (`pathway-template`,
  `syllabus-units`) plus the new `skill-graph.schema.md` (`07-…`), reason
  codes, Pydantic + fixtures (incl. cycle, dangling-capstone,
  orphan-island, and skill-graph-cycle invalids), `make schemas`.
- **KT-B — skill graph + generator + kernel.** Curated
  `skill_graph_v1.json` rows for every skill reachable from the seed
  pathways' slot seeds (content quarry: the career-track-expansion skill
  lists and their "typical arc" prose — most nodes are taxonomy rows the
  research already named), the `tools/` generator + `make trees` /
  `trees-check` per `07-…`, the committed tree artifact for the seed
  pathways, `tree_state` in `narrative/`, `honed_fraction` prior in
  `tuning.toml` + threshold-change-log entry, exhaustive tier tests (each
  transition, precedence, actual-vs-planned minutes) + generator
  determinism tests (byte-identical re-run, tie-break fixtures).
- **KT-C — strategist + API.** Prompt vocabulary + output gate,
  composition-root wiring, `tree` block in the coverage payload,
  validation tests per reason code.
- **KT-D — the map.** SVG renderer + drawer + states + vitest, built to
  `docs/design-reference/Loop - Pathway Map.html` (port its markup/CSS onto
  the SPA's real tokens; don't redesign); CDP smoke:
  select pathway → approve plan → complete a task → node flips to
  `training`/`honed` in a real browser. Definition-of-done items from
  `04-…` extend verbatim: every tier on screen must be reproducible by
  calling `tree_state` on stored data.

## Tandem note

Mechanics carry unchanged; only content shifts: coursework and
activity-shaped nodes, multi-year branches, capstones = application pillars.
The counselor/sponsor surface may show **branch counts only** (never node
detail) under existing permission tiers — the map itself stays
user-private. Tree size may grow (~60 nodes over four years); the renderer
budget should assume that ceiling now.

## Open decisions (adds to the README list)

- **d1 · Tier names**: `Locked / Discovered / Training / Honed / Proven`
  proposed — flavorful but honest; alternatives welcome before KT-A copy
  lands.
- **d2 · Honed basis**: minutes-fraction (proposed, telemetry-native) vs
  all-linked-modules-complete (stricter, punishes replans). Prior 0.8
  either way, tunable.
- **d3 · Locked state at all?** Display-only locks still read as gates to
  some users; alternative is rendering everything `discovered`. Proposed:
  keep `locked` — the reveal moment is most of the RPG feel — and revisit
  after dogfood.
- **d4 · Tree size**: 20–40 nodes per Loop pathway, Tandem ceiling 60 —
  enforced by the generator as a loud failure, never silent pruning
  (`07-…`); the knob is seed-list size and graph granularity, not
  per-tree drawing.
- **g1–g3 · Generation decisions** (transitive reduction, hand-override
  policy, blurb home): see `07-tree-generation.md`.
