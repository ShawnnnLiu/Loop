# 07 · Map Generation — Groups from a Curated Skill Grouping

First written 2026-07-17 for the DAG design; **reworked 2026-07-19 with
`06-…`'s pivot to groups** (filename kept so links stay stable). Same
status as the rest of the folder: **planning only, nothing implemented.**
The per-pathway knowledge map is emitted by a pure function from two
curated inputs: a versioned **skill grouping** and per-slot seed skills.
The prerequisite-edge skill graph, closure computation, depth assignment,
transitive reduction, and cycle handling from the first draft are
**deleted, not deferred** — grouping removes the entire class of problem.

## Why generated, not hand-drawn (unchanged argument, cheaper mechanics)

Hand-curating maps is O(pathways) and drifts: the same `skill.rag` ends up
placed differently in two pathways for no auditable reason. Generation
moves curation one level down, to O(skills): a group assignment, a minutes
prior, and a blurb are curated **once per `skill_id`** and reused by every
map. A new pathway costs 4–6 seed lists; a new career track costs its
taxonomy slice plus grouping rows. Shared skills get identical placement
in every map.

The honest split, stated once: **the method is deterministic; the
knowledge stays curated.** LLM/corpus research may *draft* grouping rows
(the career-track-expansion profiles are the quarry, per the RI-F
enrichment discipline); human review is the gate; the generator only ever
arranges reviewed facts.

## Input 1 — the skill grouping (new versioned artifact)

New spec `skill-grouping.schema.md` (proposed; authored in KT-A). A
versioned overlay **beside** the taxonomy — the shipped `skill-taxonomy`
contract, its prompt slices, and its eval-recording pinning are untouched.

`backend/taxonomy/skill_grouping_v1.json`:

```json
{
  "skill_grouping_version": "skill-grouping-v1",
  "taxonomy_version": "skill-taxonomy-v1",
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

| Field | Semantics |
| --- | --- |
| `taxonomy_version` | the pinned taxonomy the grouping was curated against; every `skill_id` must resolve in it |
| `group_id` (on entry) | the one group the skill belongs to — membership is a function, so cycles are structurally impossible |
| `expected_minutes` | per-skill prior for the honed threshold (`> 0`); flows into the map node verbatim |
| `blurb` | 1–2 sentence display description; flows into the node/group verbatim; prose, never parsed |

Invariants (contract + registry tests, invalid fixtures for each):
`skill_id`s unique and resolving against the pinned taxonomy;
every entry's `group_id` declared in `groups`; group ids unique; prestige
denylist over all text (shared constant). Coverage is **demand-driven**:
the grouping needs a row for every skill reachable from any registered
pathway's slot seeds — a seeded skill without a row fails generation with
`SKILL_GROUPING_MISSING_ENTRY`, never a silently synthesized placement.
This same lookup places taxonomy-picked user additions at runtime
(`06-…` overlay), so demand-driven coverage extends to the track's full
add-picker slice — state the widened coverage test loudly in KT-B.
(User-*created* personal groups/nodes are user-placed free-form content
and never touch the grouping or the generator; `06-…` content classes.)

Versioning follows the taxonomy discipline exactly: append-only file
versions, human review is the gate, LLMs never extend it at runtime.
Only `swe`/`mle`/`ai_engineer` have curated taxonomy slices today; an
expansion track's pathways cannot generate until its slice and grouping
rows land (interlock with `../career-track-expansion/`, one review).

## Input 2 — slot seeds (unchanged)

`EvidenceSlot.branch_skill_ids` (`02-…` §3): the 3–6 curated target skills
of that pillar. A template registered for generation must give every slot a
non-empty seed list (`SLOT_SEEDS_MISSING`); each member resolves against
the pinned taxonomy. Seeds have no control-plane effect.

## The generator — a pure function, every tie-break named

`generate_map(template, skill_grouping, taxonomy) → KnowledgeMap`. Steps,
fully deterministic:

1. **Resolve.** For each slot in template order: each seed skill → its
   grouping row → its group. Missing row → `SKILL_GROUPING_MISSING_ENTRY`.
2. **Include.** An included group brings **all its member skills that have
   grouping rows** (curated groups are small — the 4–8 guideline in
   `06-…` d4 — so a seed pulls in its natural neighbors; that is the
   point of grouping).
3. **Branch assignment.** A group seeded by exactly one slot takes that
   slot's `branch`; a group seeded by two or more takes `core`. No trunk
   computation — shared groups *are* the trunk.
4. **Capstones.** One per slot, branch-level, from the slot title — no
   edges to attach; the capstone's state comes from slot coverage, exactly
   as in `06-…`.
5. **Node fields.** `node_id` = `kn-` + the `skill_id` suffix; `group_id`
   = the grouping row's group; title from taxonomy `display_name`;
   `expected_minutes` and `blurb` from the grouping row. Any id collision
   fails generation; the KT-A uniqueness invariant is the backstop.
6. **Budget (d4), loudly.** Skill nodes above the ceiling (40 Loop, 60
   Tandem) → `KNOWLEDGE_MAP_BUDGET_EXCEEDED`; the fix is trimming seeds or
   splitting oversized groups, never silent pruning. Below ~20 nodes is an
   advisory log line, not a failure.
7. **Canonical output.** Groups sorted by (branch: `core` first, then slot
   order; `group_id`), nodes by (`group_id`, `skill_id`), canonical JSON,
   no timestamps: same inputs → byte-identical bytes.

The output must satisfy every `06-…` contract invariant — those invariants
and their invalid fixtures double as the generator's acceptance tests.

## Build-time tool — committed output, `--check` guard

`tools/generate_knowledge_maps.py`, wired as `make maps` (write) and
`make maps-check` (regenerate in memory, byte-compare — CI guard). The
`export_schemas.py` doctrine verbatim: deterministic generator, committed
output, drift reviewable in PRs.

- Output: one committed JSON artifact (proposed:
  `backend/pathways/knowledge_maps.json`, keyed by `pathway_id`; exact
  placement is a KT-B decision). It stamps `skill_grouping_version`,
  `taxonomy_version`, and the pathway-registry version; `maps-check` fails
  when any input changed without regeneration.
- The pathway registry loads the artifact at import and attaches each map
  to its `PathwayTemplate`; the composed object is validated by the
  ordinary KT-A contract. *Nothing* produces a map at runtime — runtime
  only appends user overlay records (`06-…`), which are per-account state,
  not registry content.
- Review model: a grouping edit's PR diff shows the resulting map changes
  in the artifact. Version bumps never silently reshape a live user's map
  (pinned-version discipline of `PathwaySelection`); and because the
  account overlay is add-only, a re-pin can only ever *add* nodes to what
  a user sees — removals stay registry-side proposals a user never
  experiences retroactively.

## What the generator never does

- **No LLM at generation time.** Drafting grouping rows is offline
  research; the tool consumes reviewed literals only.
- **No runtime generation.** Maps are committed artifacts; the API serves
  what review approved plus the user's own overlay.
- **No control-plane effect.** The `06-…` non-interference rule is
  untouched.
- **No silent pruning, no invented skills.** Every skill node is a
  taxonomy row placed by a reviewed grouping row; every bound violation is
  a loud typed failure.

Structured violations (all build/registry-time; none can occur at
runtime): `SKILL_GROUPING_MISSING_ENTRY`, `SLOT_SEEDS_MISSING`,
`KNOWLEDGE_MAP_BUDGET_EXCEEDED`. (`SKILL_GRAPH_CYCLE` from the first
draft is gone — membership is a function; there is nothing to cycle.)

## Increment impact (normative details live in `06-…`)

- **KT-A** authors `skill-grouping.schema.md`, its Pydantic contract, and
  fixtures (missing-entry, undeclared-group, duplicate-id invalids).
- **KT-B** curates grouping rows for every skill reachable from the seed
  pathways' slots (plus the widened add-picker coverage), builds the
  generator + `make maps`/`maps-check`, commits the map artifact, and
  lands the determinism tests.
- **KT-C / KT-D** consume maps identically regardless of origin.

## Open decisions (g-series; adds to the README list)

- **g1 · Transitive reduction** — *resolved by removal*: no edges exist.
- **g2 · Hand overrides on generated maps**: none in v1, unchanged — fix
  the grouping, not the map. Per-*user* customization (`06-…` overlay) now
  absorbs the honest use case ("my map is missing X") without reopening
  registry drift.
- **g3 · Blurb home**: grouping-only blurbs in v1 (proposed — one blurb
  per skill everywhere) vs pathway-specific framing. Same drift trade-off
  as before.
- **g4 · Group granularity**: 4–8 skills per group proposed (matches d4's
  budget arithmetic: ~5 groups per branch ceiling). Coarser groups mean
  fewer, heavier expansions; finer groups re-approach the old per-node
  clutter. Content review calibrates.
