# 03 · Desktop Observatory — Component Architecture

Status: planning only.
This doc turns the desktop half of `Loop - Star Atlas.html` into React components that consume the real `KnowledgeMapView`, drive rendering from the pure `lib/atlas/` functions (`01-…`, `02-…`), and reuse every shipped mutation route unchanged.
The `NodeDrawer`'s *semantics* survive; its skin changes.

## What stays, what changes

Keep (reuse verbatim):

- `screens/Pathway.tsx` — the route owner, fetch, and client state.
  Its `load()` (`Promise.all([api.knowledgeMap(), api.pathways()])`), `mutate(fn)` (run a mutation, swap in the returned refreshed view), `selectedNodeId`, `busy`/`error`/`actionError`, the empty-state and version-mismatch cards all remain.
  Only the child it renders changes.
- The API client (`api.knowledgeMap`, `api.setMastery`, `api.markNodeEvidence`, `api.upsertNote`/`deleteNote`, `api.addKnowledgeNode`, `api.addVocabulary`, `api.createCustomGroup`/`deleteCustomGroup`, `api.createCustomNode`/`deleteCustomNode`).
- `lib/knowledgeMap.ts`'s *view-model* helpers (`partitionGroups`, `branchGroups`, `coreGroups`, `groupNodes`, `groupCountLabel`, `branchCountLabel`, `isMastered`, `SETTABLE_TIERS`, `canMarkEvidence`) — pure map logic that is renderer-agnostic.
  Only `tierTone` is retired (replaced by `lib/atlas/bodyFor`).

Replace:

- `components/KnowledgeMap.tsx` (the DOM accordion) → the desktop `Observatory` + the mobile `MobileSky` (`04-…`), chosen by a responsive breakpoint.
- `components/NodeDrawer.tsx` → re-skinned to the atlas drawer (same dialog contract, same actions, atlas visuals + the new signal cards).

## Component tree (desktop)

```
Pathway (screen, unchanged owner)
└─ KnowledgeMapView router  ──breakpoint──▶ Observatory (desktop) | MobileSky (mobile, 04-…)
   Observatory
   ├─ <AtlasDefs/>            // the shared <svg> defs: gradients + clip-p14 (once)
   ├─ SkyChart               // the <svg viewBox="0 0 1180 665"> instrument
   │  ├─ <SkyPan>            // the pan/zoom group (focus glide); everything below scales together
   │  │  ├─ DustLayers       // two seeded parallax layers (aria-hidden)
   │  │  ├─ Nebulae          // regions from layoutSky().regions (aria-hidden)
   │  │  ├─ RegionLabels     // italic serif branch labels (real text)
   │  │  ├─ Beacons          // capstones: BeaconGlyph + label (role=button)
   │  │  ├─ Systems          // stars: StarGlyph + count chip (role=button); open → orbit ring + PlanetGlyphs
   │  │  ├─ Planets          // worlds for open systems (role=button); comets for personal
   │  │  ├─ Probe            // drift craft to next_session_at (aria-hidden; omitted if null)
   │  │  └─ Bloom            // one-shot supernova on tier-up (aria-hidden)
   │  ├─ Ornaments           // bezel ticks, corner brackets, orrery, mission plaque (aria-hidden + plaque text)
   │  └─ Vignette            // g-vig overlay (pointer-events none)
   ├─ Tooltip               // pointer-follow name+status (aria-hidden; the drawer is the accessible detail)
   └─ Overlay               // empty / "nothing lit yet" / no-pathway states
   AtlasDrawer (rendered by Pathway when selectedNodeId set) — re-skinned NodeDrawer
```

`StarGlyph`, `PlanetGlyph`, `BeaconGlyph`, `CometGlyph` are thin, declarative SVG components driven entirely by the `lib/atlas` descriptors (`starFor`, `bodyFor`, `beaconFor`) — no logic in the JSX, so they are trivially reviewable and the *math* is what's unit-tested.

## Rendering flow

1. `Pathway` fetches the view (unchanged).
2. `Observatory` calls `layoutSky(view, viewport)` once per view + open-set change, memoized.
3. For each region/system/capstone/planet, it looks up the position and hands the node/group + its `signals` (the `02-…` fields, defaulted to null) to the matching glyph.
4. Open/closed state is client-side only (`openGroups: Set<groupId>`, exactly today's model) — no fetch on expand.
5. Selection (`selectedNodeId`) drives both the drawer and the focus glide.

## Interactions (parity with the demo, wired to real routes)

- **Click a system star** → toggle it open/closed (client state); when opening, set it as the pan focus so the sky glides it to centre, clear of the drawer.
  A small `✕` on an open system re-collapses it.
- **Click a world / capstone** → set `selectedNodeId`; the drawer opens; the focus glides to its system.
- **Hover** (desktop only) → tooltip with title + `statusLine` (honest status); dust parallax tracks the pointer.
  Both are decorative — the drawer is the accessible path.
- **Drawer actions**, each an existing route through `Pathway.mutate`:
  - Adjust mastery set-point → `api.setMastery` (the only path *down*; `SETTABLE_TIERS`, `proven` never offered).
  - Mark evidence → `api.markNodeEvidence` (honed non-personal skill only; the sole path to `proven`).
  - Save/clear note → `api.upsertNote` / `api.deleteNote` (`✎` glyph then shows on the world).
  - Delete custom node → `api.deleteCustomNode`.
- **Map-level create/add**, from a toolbar above or beside the chart (the demo tucks these in-chart; on the product screen a small action row is clearer and more accessible):
  - Add a skill (picker) → `api.addVocabulary` then `api.addKnowledgeNode` — a pathway node; it lands in its grouping-defined system (`07-…`) and the sky re-lays-out.
  - New group → `api.createCustomGroup`; New node → `api.createCustomNode` (into any group).
- A tier change returned by any mutation triggers the one-shot bloom on that world (unless reduced motion), then the drawer refreshes.

## Focus pan / zoom (glide a system clear of the drawer)

The demo's `panTarget`/`applyPan` model carries over: when a system (or capstone) is focused, translate + modestly scale the `SkyPan` group so the focused body sits in the visible half not covered by the ~356px drawer, clamped so the sky never shows its edges.
Under reduced motion the transform applies instantly (no glide).
The bezel, ticks, brackets, orrery, plaque, and vignette live **outside** `SkyPan` (they are the instrument, not the sky) so they never pan or zoom — matching the demo.

## Empty and edge states (reuse `Pathway`'s existing branches)

- **No pathway selected** (`has_selection === false`) → the "uncharted space" overlay: a faded/starless rim with "No pathway charted yet" and a CTA into pathway selection (today's empty-state card content, re-skinned).
- **Fresh selection, nothing lit** (a map exists, every node `discovered`) → "Nothing lit yet — schedule your first session and first light follows," with a "Light one star" affordance that routes to scheduling (not a fake state change).
- **Version mismatch** (`version_mismatch === true`) → keep today's re-confirm card (calls `api.selectPathway`, reloads) above the chart.
- **Flourishing** end state needs no special case — it is just a fully-lit sky.

## Accessibility (desktop specifics — deferred to SA-F; see `01-…`)

> **Deferred (decision C).** The chart-body keyboard/SR work below is the SA-F target, not built in SA-C. What ships in SA-C: the real-text plaque/count summary, the accessible drawer (its dialog semantics already exist), and shape-encoded tiers. The focusable-bodies / Tab-order / focus-management items are SA-F.

- The `<svg>` chart has `role="group"` and an `aria-label` naming the pathway; the **mission-plaque text** and the header count chips are the real, readable summary.
- Systems, worlds, and capstones are focusable controls with composed accessible names ("Retrieval fundamentals — Training, 2 of 4 sessions"); Tab order follows reading order (regions top-to-bottom, systems within, then open worlds).
- The tooltip and every ornament/nebula/dust layer are `aria-hidden`.
- Focus ring: the existing dashed `.selring` becomes the visible focus indicator, honoring `:focus-visible`.
- The drawer stays a focus-trapped `role="dialog"`, Esc-closable, returning focus to the invoking body on close.

## Performance

One `<svg>`, one memoized `layoutSky`, glyphs re-render only when their node/signals change.
Loops are CSS animations (as in the demo), so they cost no React renders.
Target: a 40-node map renders and re-lays-out under a frame budget on a mid laptop; the pan glide is a CSS transform (compositor-only).
