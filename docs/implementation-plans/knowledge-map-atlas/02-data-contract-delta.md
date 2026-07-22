# 02 · Data Contract Delta and the Layout Engine

Status: planning only.
This is the engineering crux.
The `Loop - Star Atlas.html` demo is a fixture: it hand-places coordinates and hard-codes signals the real system does not carry.
Turning it into a product screen means (A) a deterministic layout engine that positions a *real* map, and (B) a small, additive, deterministic extension of the read payload for the encodings the demo fakes.
Neither weakens an axiom: layout is a pure view concern, and every new field is server-computed from stored records — no LLM, no scores, honest counts intact.

---

## Part A — the deterministic layout engine

### The gap

The generated `KnowledgeMap` (see `narrative-pathways/07-…`) is pure membership: branches (evidence slots + `core`), groups with `member_node_ids`, one capstone per slot.
`KnowledgeMapView` adds tiers and honest counts.
**Neither carries any coordinate.**
The demo's tidy 8 groups / 19 worlds / 4 regions with bespoke `x/y` is not what a user has; a real Loop pathway is 20–40 skill nodes across 3–6 evidence slots plus `core` and a personal layer (`06-…` d4).
So the sky must be *computed*, and computed the same way every render (stability, testability, no layout jitter between fetches).

### The function

A pure module `lib/atlas/layout.ts` (React-free, vitest-covered, SA-B):

```
layoutSky(view: KnowledgeMapView, viewport: {w, h}) → PositionedSky
```

where `PositionedSky` carries, in canonical order:

```
{
  regions:   { branch, cx, cy, rx, ry, grad, labelX, labelY }[]   // nebulae, one per non-core branch
  capstones: { nodeId, branch, x, y }[]                            // beacon at each region head
  systems:   { groupId, x, y }[]                                   // star per group (incl. core, personal)
  planetsFor(groupId): { nodeId, x, y, angle }[]                   // members on a 64px orbit when open; at star centre when collapsed
}
```

Every output is a deterministic function of the view's *structure* (ids, membership, branch assignment, counts) and the viewport — never of tier or of fetch order, so tiers can change without the sky reshuffling.

### The algorithm (force-directed, made deterministic — decision A)

Canonical viewBox `1180 × 665` (the demo's), scaled to the container by SVG `viewBox`, so math is resolution-independent.
A force-directed relaxation adapts to any real map shape (odd branch counts, dense groups) far better than a fixed table would — the decision the user took (README decision 2).
The one hard requirement it must not lose is **determinism**: same map → byte-identical positions, so the sky never jitters between fetches and the output is snapshot-testable.
Force-directed layout is deterministic **iff** its seed positions and its iteration count are fixed and it uses no randomness — which this environment enforces anyway (`Math.random`/`Date.now` are unavailable).
The design below spends its whole budget on that guarantee.

1. **Order everything canonically.**
   Non-core evidence slots in `view.branches` order; then `core`; the personal layer last, outside the pathway field.
   Groups within a branch in `branchGroups` order; members within a group in `member_node_ids` order.
   All seeding and iteration walk these canonical orders, so input-array order never affects output.
2. **Seed region anchors from a demo-derived table (fixed, not simulated).**
   Each branch gets a nebula anchor (centre + radii + gradient) from a lookup keyed by non-core branch count `n ∈ {1..6}`, distributed across the canvas (1 → centre; 2 → left/right; 3 → triangle; 4 → quadrants; 5–6 → ring), seeded from the demo's region centroids so the *overall composition* echoes the hero.
   `core` anchors at canvas centre; personal anchors bottom-right, beyond the nebulae.
   Region anchors are **fixed** — they are not relaxed — so the nebula clusters stay stable and legible; only the bodies inside them move.
3. **Seed body positions deterministically.**
   Each system (group star) starts near its branch's region anchor, offset by a golden-angle spiral indexed by its canonical position (a fixed, RNG-free spread).
   Each capstone starts at its region head (a fixed offset from the region anchor toward the nearer canvas edge).
   Members start at their system's seed (they only separate when the system is open).
4. **Relax with a fixed-step force simulation.**
   Run exactly `ITER` iterations (a fixed constant, e.g. 300) of: pairwise **repulsion** between all systems + capstones (and, within an open system, between its planets); **spring attraction** of each system toward its region anchor and of each open system's planets toward a 64px orbit ring around their star; **containment** forces keeping every body inside the rim and clear of the drawer zone on the right.
   No cooling randomness, no time term — a fixed integration step over a fixed iteration count is a pure function of the seeds.
   Rounding to a fixed decimal precision at the end absorbs float drift so the output is exactly reproducible.
5. **Place planets (members) of a system.**
   Collapsed → all members collapse back to the star centre (they animate out on open); the simulation only spreads planets for *open* systems, so `planetsFor(groupId)` returns star-centre coords when collapsed and the relaxed orbit coords when open.
6. **Deterministic output.**
   Same view + viewport → identical `PositionedSky`; arrays in canonical (branch, then group id, then member id) order; coordinates rounded to fixed precision.

Divergence from the demo (surfaced): because bodies are *relaxed*, not hand-placed, the reference pathway will **not** reproduce the demo's exact pixel positions — it echoes the hero *composition* (region clusters seeded from the demo, systems fanned, worlds orbiting), not its literal coordinates.
This is the deliberate trade the decision makes: shape-adaptivity and no per-shape table tuning, at the cost of exact hero reproduction.

### Overlap and scale policy

Repulsion is the primary overlap defence — dense regions spread themselves.
`layoutSky` runs a post-simulation minimum-separation check; if any two systems (or two open planets) settle closer than the legibility threshold, it raises repulsion strength and re-runs the fixed iteration count once more (still deterministic — a fixed second pass, not an open loop).
Beyond the map budget (`06-…` d4: 40 nodes / ~8 groups per Loop pathway, enforced loudly at *generation* time in `07-…`), no runtime map should exceed what the simulation separates cleanly.
If one ever does — separation still unmet after the second pass — the renderer logs a visible advisory and falls back to a plain deterministic grid of systems: never a scrambled sky, never a silent crop.

### Tests (SA-B, vitest)

- **Determinism**: `layoutSky(view)` twice → deep-equal, and a committed **snapshot** of the reference-pathway output is byte-stable across runs (the force sim's fixed seed + fixed `ITER` guarantee this; the snapshot is the regression guard).
- **Composition fidelity** (replaces exact hero fidelity): the reference pathway's systems each settle inside their seeded region ellipse, and the branch → region assignment matches the demo's clustering — legibility and clustering, not literal coordinates.
- **Shape sweep**: fixtures for `n = 1..6` branches × `3..12` groups × `2..8` members assert no two systems (and no two open planets) sit closer than the legibility threshold after relaxation, every body stays inside the rim and clear of the drawer zone, and every node/group/capstone gets exactly one position.
- **Order stability**: shuffling `view.nodes`/`view.groups` input order does not change any output coordinate (seeding walks canonical id order, not input order).
- **Convergence bound**: the fixed `ITER` count is sufficient for the shape-sweep fixtures to meet separation without the grid fallback; the fallback fires only on the deliberately over-budget fixture.
- **Collapsed vs open**: `planetsFor` returns star-centre coords when the group is collapsed, relaxed orbit coords when open.

Mobile needs no layout engine — the mobile treatment is a scrolling DOM list grouped by branch (`04-…`), so `layoutSky` is desktop-only.

---

## Part B — the data-contract delta

### What the payload already carries (enough for the base atlas)

`KnowledgeNodeView` today: `node_id`, `title`, `kind` (`skill`/`capstone`/`custom`), `tier`, `group_id`, `branch`, `skill_id`, `expected_minutes`, `blurb`, `description`, `note`, `linked_module_ids`, `is_personal`.
`KnowledgeGroupView`: `honed_count`, `total_count`, `branch`, `is_personal`, `member_node_ids`.
`KnowledgeBranchView`: `slot_id`, `title`, `capstone_node_id`, `capstone_tier`, `honed_count`, `total_count`.

That is sufficient to render: all four base planet states, star brightness/warmth, count chips, region light-pollution, the constellation, comets, the mission plaque, the `✎` note glyph (from `note`), and every drawer field the current `NodeDrawer` already shows.
**The base re-skin (SA-B/C/D) needs no backend change beyond the SA-A signals it reads.**

### What the five richer encodings need (SA-A, additive, nullable — lands first)

Each is a deterministic, server-computed signal — no LLM, no score — added to `KnowledgeNodeView` (and one to the branch view).
All are optional/nullable so the frontend reads them defensively — a signal that is absent for a given node (no scheduled session, no evidence yet) simply drops its flourish (see the degradation contract below).
Spec-first per CLAUDE.md: amend the `app/results.py` model, compute in `app/cycle.py::knowledge_map_view` from data the service already holds, add backend tests, `uv run make check`.

| Encoding | New field(s) | Deterministic source | Degradation when null |
|---|---|---|---|
| **Orbital session trail** (arc segments on a `training` world) | `sessions_total: int \| None`, `sessions_done: int \| None` | The node's `linked_module_ids` → the active plan's tasks for those modules → scheduled count (total) and telemetry-confirmed count (done). Both already live in the plan + telemetry stores the service reads. | Render the base training planet (ember + magma) with **no** trail. Honest: "under way," count unknown. |
| **Probe to next session** | `next_session_at: datetime \| None` (on the view or per node) | The earliest scheduled start among the node's linked tasks (tz-aware ISO, like every other datetime the SPA localizes). | Omit the probe and the "next session" chip entirely. |
| **Proven evidence card** | `evidence_label: str \| None`, `evidence_confirmed_at: datetime \| None` | The confirmed evidence anchor that flipped the node to `proven` (the mark-evidence record / matched evidence item). Store an opaque label, never raw calendar text. | Proven world still crowns; the drawer shows no file card. |
| **Review shimmer** | `review_flagged: bool` (default `false`) | The mastery-memory review flag (`08-…`: honed-but-shaky from low `solve_confidence`). Already a deterministic fold input. | No shimmer; still honed. |
| **Self-assessed tick** | `self_assessed: bool` (default `false`) | True when the node's tier equals its `MasterySetPoint` target and exceeds what derived study alone would give (the fold already distinguishes set-point from telemetry). | No tick; tier still shown honestly. |

Notes:

- These are **read-payload** additions only.
  No mutation route changes; the atlas reuses `setpoint`, `mark-evidence`, `note`, add-node, custom CRUD verbatim.
- `sessions_total/done` and `next_session_at` are the same numbers the Today/Week screens already derive from the plan — SA-A is surfacing existing truth onto the node, not computing anything new about mastery.
- Capstones keep no session/evidence-minutes fields (they have none, `06-…`); `evidence_label` on a capstone is its confirmed artifact label, mirroring the skill case.
- The TS mirrors in `api/types.ts` grow the same optional fields; `lib/atlas/` reads them defensively (`?? null`).

### The graceful-degradation contract (normative for this plan)

Even though SA-A lands the signals first, the frontend must never *depend* on a signal being present for a given node: a training world with no session scheduled yet, a honed world with no evidence, a capstone with no session fields.
Concretely: `bodyFor`/`starFor`/`beaconFor` take a `signals` object whose fields are all optional; a missing signal removes its flourish and never fabricates a placeholder.
This keeps the renderer robust to partial data and decoupled from field-by-field backend timing, and it keeps the axiom line clean: the map never shows a session count, a next-session time, or an evidence file it did not receive from the deterministic service.

### What must NOT change

- `map_state` and the mastery fold (`narrative/mastery.py`) — meaning is fixed by `06-…`/`08-…`.
- Honest counts: no field added here is a percentage, average, or score.
- Non-interference: none of these signals feeds routing, scheduling, or task availability; they are presentation only.
- The overlay store and every mutation contract.
