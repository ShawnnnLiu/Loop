# 07 · Tree Generation — Deterministic Trees from a Curated Skill Graph

Added 2026-07-17, same status as the rest of the folder: **planning only,
nothing implemented.** This doc amends `06-…`: the per-pathway knowledge
tree is no longer hand-drawn content — it is **emitted by a pure function**
from two curated inputs (a versioned skill graph and per-slot seed lists).
Everything else in `06-…` is unchanged: the `KnowledgeTree` contract, the
mastery-tier ladder, the plumbing, the map UI, and the non-interference
rule all apply verbatim to generated trees.

## Why generated, not hand-drawn

Hand-curating a DAG is O(pathways): 20–40 nodes × 2–4 pathways per track ×
every future track, each with edges, depths, minutes, and blurbs drawn by
hand — and open decision d4 already names curation cost as the binding
constraint. Worse, hand-drawn trees drift: the same `skill.rag` can end up
with different prerequisites in two pathways for no reason a reviewer can
audit.

Generation moves the curation one level down, to O(skills): prerequisite
edges, a minutes prior, and a blurb are curated **once per `skill_id`** and
reused by every tree that touches that skill. A new pathway costs 4–6 seed
lists; a new career track costs its taxonomy slice plus graph rows, and
every pathway on it generates. Shared skills get identical structure in
every tree, and "natural progression" stops being an aesthetic judgment —
it is the topological order of the prerequisite DAG.

The honest split, stated once: **the method is deterministic; the knowledge
stays curated.** A generator that invented structure from nothing would
just be LLM curation with extra steps — exactly the axiom-08 wall this
folder keeps. LLM/corpus research may *draft* graph rows (the
career-track-expansion profiles' "typical arc" prose and interview-loop
stages are the quarry, per the RI-F enrichment discipline); human review is
the gate; the generator only ever rearranges reviewed facts.

## Input 1 — the skill graph (new versioned artifact)

New spec `skill-graph.schema.md` (proposed; authored in KT-A under the
spec-first workflow). A versioned overlay **beside** the taxonomy — the
shipped `skill-taxonomy` contract, its prompt slices, and its eval-recording
pinning are untouched; edges are generator-facing, never prompt-facing.

`backend/taxonomy/skill_graph_v1.json`:

```json
{
  "skill_graph_version": "skill-graph-v1",
  "taxonomy_version": "skill-taxonomy-v1",
  "entries": [
    {
      "skill_id": "skill.rag",
      "prerequisite_skill_ids": ["skill.python", "skill.llm-apis"],
      "expected_minutes": 360,
      "blurb": "How dense and lexical retrieval differ, and when each wins."
    }
  ]
}
```

| Field | Semantics |
| --- | --- |
| `taxonomy_version` | the pinned taxonomy the graph was curated against; every `skill_id` (including prerequisites) must resolve in it |
| `prerequisite_skill_ids` | what to learn first; edges of a global DAG over taxonomy ids (may be empty — roots are the basics) |
| `expected_minutes` | per-skill prior for the honed threshold (`> 0`); flows into the tree node verbatim |
| `blurb` | 1–2 sentence display description; flows into the tree node verbatim; prose, never parsed |

Invariants (contract + registry tests, invalid fixtures for each):

- `skill_id`s unique; every id and every prerequisite id resolves against
  the pinned taxonomy version (completeness test, same pattern as theme
  membership).
- Edges form a **DAG**; no self-prerequisites — cycle → structured
  violation `SKILL_GRAPH_CYCLE` (lift the DFS from `validation/graph.py`,
  the same one `KNOWLEDGE_TREE_CYCLE` reuses).
- Prestige denylist over blurbs (shared constant).
- Coverage is **demand-driven**, not total: the graph needs a row for every
  skill reachable from any registered pathway's slot seeds, not for all 166
  taxonomy entries. A reachable skill without a row fails generation with
  `SKILL_GRAPH_MISSING_ENTRY` — never a silently synthesized node.

Versioning follows the taxonomy discipline exactly: append-only file
versions, human review is the gate, LLMs never extend it at runtime.
Track dependency stated plainly: only `swe`/`mle`/`ai_engineer` have
curated taxonomy slices today; an expansion track's pathways cannot
generate until its slice and graph rows land (interlock with
`../career-track-expansion/`, one review).

## Input 2 — slot seeds

`EvidenceSlot` (amendment in `02-…` §3) gains `branch_skill_ids`: the 3–6
curated target skills of that pillar — the competencies the capstone
artifact demonstrates. Seeds are the only per-pathway tree curation left.
A template registered for generation must give every slot a non-empty seed
list (`SLOT_SEEDS_MISSING` otherwise); each member resolves against the
pinned taxonomy (registry-completeness test). Seeds have no control-plane
effect — they exist for the generator alone.

## The generator — a pure function, every tie-break named

`generate_tree(template, skill_graph, taxonomy) → KnowledgeTree`. Steps,
fully deterministic:

1. **Closure.** For each slot in template order: `closure(slot)` = its
   `branch_skill_ids` plus all transitive prerequisites via the graph.
   Any skill encountered without a graph row → `SKILL_GRAPH_MISSING_ENTRY`.
2. **Branch assignment.** A skill in exactly one closure joins that slot's
   branch; a skill in two or more joins `core` (the shared trunk — shared
   prerequisites *are* the trunk, by construction, not by hand).
3. **Edges.** For every included skill, an edge from each included
   prerequisite to it (prerequisite → dependent, i.e. capstone-ward,
   matching the `06-…` edge example). Then transitive reduction (open
   decision g1) — closure edges add clutter, not information.
4. **Depth.** `depth(node)` = length of the longest chain of included
   prerequisites ending at it (longest-path topological level over the
   included DAG). Roots — the basics — land at depth 0, trunk-adjacent,
   exactly as `06-…` defines the field. This is the "natural progression":
   layout order *is* dependency order.
5. **Capstones.** One per slot, `depth` = max depth in its branch + 1.
   Every sink (included node with no outgoing edge) gets an edge to the
   capstone of each slot whose closure contains it — which preserves the
   `06-…` every-node-reaches-a-capstone invariant, including for a shared
   seed that landed in `core`.
6. **Node fields.** `node_id` = `kn-` + the `skill_id` suffix (drop the
   `skill.` prefix — the id grammars line up); capstone `node_id` =
   `kn-<slot_id>-capstone`; title from taxonomy `display_name` (capstones:
   slot title); `kind` = `skill` always (see the `concept` note below);
   `expected_minutes` and `blurb` from the graph row (capstones carry
   neither, per the `06-…` example — their state comes from slot coverage).
   Any id collision fails generation; the KT-A uniqueness invariant is the
   backstop.
7. **Budget (d4), loudly.** Total nodes above the ceiling (40 Loop, 60
   Tandem) → `KNOWLEDGE_TREE_BUDGET_EXCEEDED`; the fix is trimming seeds
   or coarsening graph granularity, never silent pruning (the house
   no-silent-caps rule). Below the 20-node guideline is an advisory log
   line, not a failure — a sparse pathway is honest.
8. **Canonical output.** Nodes sorted by (branch: `core` first, then slot
   order; depth; `skill_id`), edges by (`from`, `to`), canonical JSON
   serialization, no timestamps: same inputs → byte-identical bytes.

The output must satisfy every `06-…` contract invariant (DAG, unique ids,
one capstone per slot, no orphan islands, denylist) — those invariants and
their invalid fixtures double as the generator's acceptance tests. The
contract rejects a bad tree no matter who produced it.

## Build-time tool — committed output, `--check` guard

`tools/generate_knowledge_trees.py`, wired as `make trees` (write) and
`make trees-check` (regenerate in memory, byte-compare against the
committed artifact — CI guard). This is the `export_schemas.py` doctrine
verbatim: deterministic generator, committed output, drift reviewable in
PRs.

- Output: one committed JSON artifact (proposed:
  `backend/pathways/knowledge_trees.json`, keyed by `pathway_id`; exact
  placement is a KT-B decision like the registry module's). It stamps the
  `skill_graph_version`, `taxonomy_version`, and pathway-registry version
  it was generated from; `trees-check` fails when any input changed
  without regeneration.
- The pathway registry loads the artifact at import and attaches each tree
  to its `PathwayTemplate`; the composed object is validated by the
  ordinary KT-A contract. Trees remain registry literals from every
  consumer's point of view — `02-…`'s "an LLM never produces one at
  runtime" now has a stronger sibling: *nothing* produces one at runtime.
- Review model: a graph edit's PR diff shows the resulting tree changes in
  the artifact — the reviewer sees concrete trees, not just abstract
  edges. Version bumps never silently reshape a live user's map, matching
  the pinned-version discipline of `PathwaySelection`.

## What the generator never does

- **No LLM at generation time.** Drafting graph rows is offline research;
  the tool consumes reviewed literals only.
- **No runtime generation.** Trees are committed artifacts; the API serves
  what review approved.
- **No control-plane effect.** The non-interference rule of `06-…` is
  untouched: generated edges suggest a learning order visually and never
  gate the Planner, the Scheduler, or task availability — axiom-11
  prerequisite computation over task dependencies remains the only unlock
  system.
- **No silent pruning, no invented skills.** Every non-capstone node is a
  taxonomy row reached through reviewed edges; every bound violation is a
  loud typed failure.

New structured violations (all build/registry-time; none can occur at
runtime, so `06-…`'s runtime reason-code list is unchanged):
`SKILL_GRAPH_CYCLE`, `SKILL_GRAPH_MISSING_ENTRY`, `SLOT_SEEDS_MISSING`,
`KNOWLEDGE_TREE_BUDGET_EXCEEDED`.

## Increment impact (normative details live in `06-…`)

- **KT-A** additionally authors `skill-graph.schema.md`, its Pydantic
  contract, and fixtures (incl. graph-cycle and missing-entry invalids).
- **KT-B** replaces "curated trees for the seed pathways" with: curated
  graph rows for every skill reachable from the seed pathways' slots, the
  generator + `make trees`/`trees-check`, the committed tree artifact, and
  generator determinism tests (byte-identical re-run, tie-break fixtures)
  — alongside the `tree_state` kernel work already listed.
- **KT-C / KT-D** are untouched: the Strategist vocabulary, the coverage
  payload, and the map renderer consume trees identically regardless of
  origin.

## Tree-node `kind` note

`06-…` defines `concept` as knowledge without a taxonomy row. Under
generation every node is taxonomy-anchored (the taxonomy's own `concept`
kind already hosts conceptual entries like `skill.rag`-adjacent theory), so
the generator emits only `skill` and `capstone` in v1. The `concept` tree
kind stays in the contract as reserved — dropping it is a KT-A copy
decision, not a mechanic.

## Open decisions (g-series; adds to the README list)

- **g1 · Transitive reduction**: on (proposed — the map reads as a
  progression, not a hairball) vs off (shows every curated edge). Either
  is deterministic; the choice is display fidelity.
- **g2 · Hand overrides on generated trees**: none in v1 (proposed — fix
  the graph, not the tree; an override channel quietly reintroduces
  per-pathway curation and lets shared skills drift apart again) vs a
  bounded per-template patch list. Revisit only if a real tree proves
  wrong in a way the graph can't express.
- **g3 · Blurb home**: graph-only blurbs in v1 (proposed — one blurb per
  skill everywhere) vs allowing pathway-specific framing. Same drift
  trade-off as g2.
