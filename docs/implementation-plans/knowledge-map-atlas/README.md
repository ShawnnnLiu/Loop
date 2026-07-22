# Knowledge Map — Star Atlas UI

Written 2026-07-21.
Status: **planning only, nothing implemented.**
This folder is the visual-implementation plan for rebuilding the shipped Knowledge Map UI to the **Star Atlas** design.

## Why this folder exists

The knowledge-map *semantics* are built and merged: KT-A … KT-D (PR #52) landed the contracts, the generator, the `map_state` mastery fold, the overlay store, the full mutation API, and a first UI at the `/pathway` route.
That first UI is a plain DOM/CSS accordion — branches → group waypoints → inline node rows — ported toward the older `docs/design-reference/Loop - Pathway Map.html` treatment.

On 2026-07-20 a new design drop replaced the map's visual source of truth: `docs/design-reference/Loop - Star Atlas.html`, an "observatory" rendering of the same map — a dark star chart where evidence branches are nebula regions, skill groups are star systems, skill nodes are worlds that warm from barren rock to living oceans as they are studied, and capstones are beacons that bloom into supernovae when proven.
The `docs/design-reference/README.md` now names Star Atlas "the **visual source of truth for the Knowledge Map**"; the Pathway Map page is "superseded … for visuals."

Nothing in `narrative-pathways/` plans that rebuild.
`06-knowledge-tree.md`'s "UI — the Knowledge Map" section still describes the warm-paper cartographer's-chart treatment and explicitly says "the canvas needs a re-pass for the group-expansion interaction before KT-D."
The Star Atlas *is* that re-pass, delivered after KT-D shipped.
This folder is the implementation plan for adopting it.

## What is normative, and what this changes

**Semantics stay normative in `narrative-pathways/06-knowledge-tree.md` and `08-mastery-memory.md`.**
The four-tier ladder (`discovered → training → honed → proven`), honest counts (never percentages or scores), the no-edges / nothing-locked rule, the two content classes (pathway vs personal), the add-only onboarding rule, the customization surfaces (add-skill, custom group/node, notes, adjust-mastery set-points, mark-evidence), and axiom-11 non-interference are all unchanged.
This plan does not touch the backend `map_state` kernel's meaning, the overlay store, or any mutation route's contract.

**This folder supersedes only the *visual* half.**
It replaces the "UI — the Knowledge Map (expandable groups in Loop's skin)" section of `06-…` and the gilding-ramp mapping in `frontend/src/lib/knowledgeMap.ts` (`tierTone`).
Where `06-…` reads "illuminated cartographer's chart" and "warm paper," read instead "observatory / star atlas."
The `Loop - Star Atlas.html` page is the visual source of truth; this doc set is normative for *how* it becomes the real, data-driven, mobile-friendly React SPA screen.

## The design, in one paragraph

The map is a dark instrument embedded in Loop's light page: a bezelled "sky" chart under the paper toolbar and header.
Each evidence-slot branch is a faint **nebula region** with an italic label; its **capstone** is a **beacon** at the region head (a caged ember when unproven, a rayed supernova corona when proven).
Each skill group is a **star system** — a star whose brightness and warmth grow with the honest count of honed members; click it and its member **worlds** bloom out on a small orbit, and the sky glides the system to centre, clear of the detail drawer.
Each world is a planet keyed to its tier: barren cratered rock (`discovered`), rock with magma cracks, an ember pulse, and an orbital session-progress trail (`training`), a living green-ocean world (`honed`), and an ocean crowned with a ring and a ✓ (`proven`).
Personal-layer nodes are **comets** — chalk-sketched, never gilded, joining no count.
The whole thing is honest: counts only, no XP, no levels; a mission-plaque cartouche states "n honed · n proven · n of m capstones proven," and mobile trades the canvas for a scrolling sky of accordion system cards with a bottom sheet.

## The hard parts (why this is more than a re-skin)

1. **No layout in the contract.**
   The `Loop - Star Atlas.html` page hand-places an `x`/`y` for every group, node, capstone, and region.
   The real generated `KnowledgeMap` (see `narrative-pathways/07-tree-generation.md`) carries *no coordinates* — only membership: branches, groups, member node ids, one capstone per slot.
   A real user's map is not the demo's tidy 8 groups / 19 worlds; it is 20–40 nodes across 3–6 branches.
   So the plan's centrepiece is a **deterministic, force-directed layout engine** — a pure function from the abstract map to a positioned sky (decision A) — made byte-stable by fixed seed positions and a fixed iteration count (no randomness, which the environment enforces anyway), and snapshot-tested so it never jitters (`02-data-contract-delta.md`).

2. **The richer encodings need data the payload does not carry yet.**
   The current `KnowledgeNodeView` has `tier`, honest counts, `blurb`, `note`, and `linked_module_ids` — enough for the four base planet states.
   The Star Atlas *also* draws an orbital trail of "sessions done / total," a drifting "probe" toward the next scheduled session, a confirmed-evidence file card on proven worlds, a "revisit?" shimmer on review-flagged nodes, and a "self-assessed" tick when a tier came from a set-point rather than derived study.
   None of those five signals is in the payload.
   `02-…` specifies the minimal *additive, deterministic, server-computed* view extensions for them; they land first (SA-A), and each stays nullable so the renderer degrades gracefully on any node whose signal is absent (no session scheduled yet, no evidence, a capstone with no session fields).

3. **An SVG star map has real accessibility and motion cost.**
   The demo is a mouse-and-eyes prototype.
   Reduced-motion is **in scope** (the design page already ships the `prefers-reduced-motion` fallbacks; porting them is nearly free).
   Full map accessibility — keyboard traversal and screen-reader semantics for the SVG bodies — is **deferred to a noted follow-up (SA-F)** to save cost now (decision C); the cheap/free pieces (real-text honest counts, the existing drawer/sheet dialog semantics, colour-never-the-only-signal via shape) are retained.
   `01-visual-language.md` carries the full accessibility spec as the follow-up's target.

## Doc map

| Doc | What it holds |
|---|---|
| `01-visual-language.md` | The observatory metaphor made precise: the normative tier → celestial-body table, star brightness/warmth math, capstone beacon/supernova states, nebula regions + mastery light-pollution, comets for the personal layer, ornaments (mission plaque, orrery, bezel, probe, constellation lines), the new design tokens to add to `tokens.css`, the light-page / dark-chart theme rule, motion + `prefers-reduced-motion`, and accessibility. **Read first.** |
| `02-data-contract-delta.md` | The engineering crux: the deterministic **layout engine** spec (abstract map → positioned sky, desktop-only, unit-testable), and the **data-contract delta** — every atlas visual encoding mapped to its source, what `KnowledgeMapView` already carries, the minimal additive backend fields the five richer encodings need, and the graceful-degradation contract. |
| `03-desktop-observatory.md` | Desktop component architecture: the SVG chart renderer decomposition, wiring the layout engine, pan/zoom focus behaviour, tooltip + parallax, the re-skinned detail drawer (reusing every existing mutation route), empty/version-mismatch states, and the (deferred, SA-F) chart-body accessibility spec. |
| `04-mobile-atlas.md` | The mobile treatment: the scrolling sky, systems as inline accordion cards, the bottom sheet, the responsive breakpoint strategy for one SPA screen (canvas ↔ scroll-list), touch-target and mobile-friendliness requirements. |
| `05-increments.md` | SA-A … SA-E increments (one commit each), the test strategy (vitest for the pure layout + tier-mapping functions; CDP smoke for the real browser), definition of done, and the risk register. |

## What's already shipped (do not rebuild)

Confirmed by reconnaissance against `main` at commit `59df20e` (PR #52 merged):

- **Read route** `GET /api/knowledge-map` → `KnowledgeMapView` (`app/web/routes_cycle.py`, model in `app/results.py`), assembled by `Service.knowledge_map_view()` (`app/cycle.py`) over the `map_state` fold (`narrative/mastery.py`).
- **Mutation routes**, all wired in today's UI and reused verbatim by the atlas: `add-node`, `add-vocabulary`, `custom-group` (create/delete), `custom-node` (create/delete), `note` (upsert/delete), `setpoint`, `mark-evidence`.
- **Frontend**: `screens/Pathway.tsx` (route owner + fetch/state), `components/KnowledgeMap.tsx` (renderer), `components/NodeDrawer.tsx` (drawer), `lib/knowledgeMap.ts` (pure view-model, vitest-covered), TS mirrors in `api/types.ts`, client fns in `api/client.ts`.

The atlas keeps the route, the fetch/state owner, the API client, and the pure view-model's *semantics*; it replaces the two rendering components and the `tierTone` gilding ramp, and grows the payload (SA-A, first) and `tokens.css` (SA-B).

## Placement note (a reconciliation)

`06-…` proposed the map live "under Progress" as an expand from the Story panel.
The shipped reality — and the Star Atlas design's own top bar (`Today · Schedule · Pathway · Check-ins`) — put the map on its **own top-level route**.
This plan keeps the shipped, design-matching top-level `/pathway` route.
The Progress screen keeps its compact Story-panel summary with a "View knowledge map" link into `/pathway` (already the pattern via `Pathway.tsx`'s "← Back to Progress").

## Divergences from the design reference (surfaced, per the design-reference README)

The `design-reference/README.md` is explicit: follow the drop for *style*, not as a spec to copy verbatim; when design and the deterministic backend disagree, the backend wins and the mismatch is surfaced.
The deliberate divergences this plan takes:

- **Computed layout, not the demo's hand-placed coordinates** (see hard part 1).
  A deterministic force-directed relaxation (decision A) positions the sky; region anchors are seeded from the demo so the *composition* echoes the hero, but bodies are relaxed, so exact hero pixels are not reproduced — the deliberate trade for shape-adaptivity.
- **Graceful degradation for the five richer encodings** (hard part 2): a null `next_session_at` simply omits the probe; absent session counts render the base training planet without the orbital trail; no `evidence_label` means the proven world still crowns but shows no file card.
  The signals land first (SA-A), but the renderer never depends on any one being present for a given node, so partial data always renders honestly.
  No encoding invents data.
- **The chart is intrinsically dark**, embedded in Loop's light page; the app has no dark theme and this plan adds none.
  The observatory bezel is the one dark surface by design intent, not a theme.
- **Reduced-motion is first-class** (in scope); **full SVG-map accessibility is deferred** to a noted follow-up (SA-F, decision C), retaining the free pieces.

## Kickoff prompt (copy-paste into a fresh session, when implementation is approved)

```
Read docs/implementation-plans/knowledge-map-atlas/README.md, then its five
numbered docs, then docs/design-reference/Loop - Star Atlas.html (the visual
source of truth) and docs/implementation-plans/narrative-pathways/06-knowledge-tree.md
+ 07-tree-generation.md (normative semantics). Then read the shipped surface:
frontend/src/screens/Pathway.tsx, frontend/src/components/KnowledgeMap.tsx,
frontend/src/components/NodeDrawer.tsx, frontend/src/lib/knowledgeMap.ts,
frontend/src/api/types.ts (KT block), frontend/src/styles/tokens.css, and the
backend GET /api/knowledge-map view in backend/src/agentic_calendar/app/results.py
+ app/cycle.py::knowledge_map_view. Implement increments SA-A through SA-E in
order, one commit per increment, following CLAUDE.md (spec/axiom-first for any
backend change, the four frontend gates green per commit — npm run typecheck /
lint / test / build — plus uv run make check from backend/ for SA-A, the
backend-signal increment that lands first; ask before networked commands or new
dependencies). Start by restating
the increments and the open decisions the docs flag, then begin SA-A.
```

## Open decisions (flagged for the user)

1. **Signal timing — RESOLVED (2026-07-21): backend signals land first.**
   The five richer encodings (session trail, probe, evidence card, review shimmer, self-assessed tick) need additive backend fields.
   Per the user's call these land **first**, as SA-A, so every rendering increment works against real data.
   The frontend still reads them defensively (the graceful-degradation contract, `02-…`), so partial data on any given node renders honestly.
2. **Layout engine — RESOLVED (2026-07-21): force-directed (decision A).**
   A deterministic force-directed relaxation (`02-…` Part A), made byte-stable by fixed seed positions + a fixed iteration count (no randomness) and snapshot-tested.
   It adapts to any real map shape rather than needing a hand-tuned per-shape table; the trade is that it echoes the demo's *composition*, not its exact pixels.
3. **Personal nodes on mobile — RESOLVED (2026-07-21): shared mini-comet (decision B).**
   Mobile personal rows render via the same `CometGlyph` mini-SVG the desktop sky uses, so a comet is a comet on both platforms and the glyph components stay shared between `Observatory` and `MobileSky` — no mobile-only personal-node vocabulary.
4. **CDP smoke coverage depth — RESOLVED (2026-07-21): functional + responsive only; accessibility deferred (decision C).**
   The SA-E smoke re-runs the KT-D flows (select pathway → open system → open world → set-point down → add vocab node → create custom node/group → mark evidence) at **both** desktop and mobile viewports and asserts the celestial state matches the honest data.
   It does **not** assert keyboard/screen-reader accessibility — that verification, together with the SVG-map a11y implementation, is deferred to the noted follow-up **SA-F** (see `05-…`).
   Reduced-motion fallbacks are still implemented (they ship in the design CSS); their dedicated CDP audit rides along with SA-F.

## Deferred follow-up — SA-F (accessibility)

Descoped now for cost (decision C), tracked so it is not forgotten.
SA-F makes the SVG map fully accessible per the `01-visual-language.md` spec: focusable celestial bodies with composed accessible names, keyboard traversal to every system/world/capstone, focus management on the map bodies (the drawer/sheet already have dialog semantics), a colour-independence pass, and the CDP assertions for keyboard-only reach and reduced-motion stillness.
Until SA-F lands, the atlas is honest and legible (real-text counts, shape-encoded tiers, accessible drawer/sheet) but not keyboard/SR-complete on the chart itself — a known, documented debt, not a silent gap.
