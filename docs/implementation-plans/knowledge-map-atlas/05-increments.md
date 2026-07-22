# 05 · Increments — SA-A … SA-E (+ deferred SA-F)

Status: planning only.
One commit per lettered increment, in order.
Every frontend commit is green on the **four frontend gates** (`npm run typecheck`, `npm run lint`, `npm run test`, `npm run build`) from `frontend/`.
The one backend increment (SA-A) is additionally green on `uv run make check` from `backend/`, spec/axiom-first per CLAUDE.md.
Ask before networked commands or new dependencies; none of these increments needs either.

## Sequencing rationale

**Backend signals lead** (the user's call, 2026-07-21): the read payload is enriched *first*, so every later increment renders the full design against real data instead of placeholders, and the frontend's signal readers are written against fields that already exist.
SA-A is the additive, deterministic signal delta — a pure backend enrichment that touches no mastery meaning.
SA-B is then the pure, fully-tested atlas foundation (the deterministic layout engine + the tier→body/star/beacon mapping + tokens), proven before a single pixel is drawn.
SA-C then SA-D build desktop then mobile on that foundation.
SA-E is ornament polish, reduced-motion, and the functional browser smoke.
Full SVG-map accessibility is descoped for cost (decision C) into the noted follow-up **SA-F**, kept as documented debt rather than dropped silently.
The graceful-degradation contract (`02-…`) is kept as a robustness property regardless of order — a missing signal removes its flourish, never fabricates one — so partial data (a training node with no scheduled session yet, a capstone with no session fields) always renders honestly.

## SA-A — backend signal delta (additive, deterministic)

**Status: IMPLEMENTED** (backend `make check` + lint/typecheck/boundaries green; four frontend gates green on the TS-mirror change).
Two scoping calls made during implementation, binding on SA-B's `signals.ts`:
- **No field was added to `KnowledgeBranchView`.** The capstone's signals ride on its own `KnowledgeNodeView` (already in `nodes`), so "where relevant" turned out to be nowhere - one node is the single signal-bearer.
- **`evidence_label` is capstone-only; skills carry only `evidence_confirmed_at`.** Mark-evidence stores a timestamped `MasteryGrant` but no label, so a proven skill honestly exposes `evidence_confirmed_at` (the grant time) with `evidence_label = null`; a proven capstone exposes `evidence_label` (its filled slot's matched confirmed-experience title) with `evidence_confirmed_at = null` (experience items carry no timestamp). SA-B's proven-card reader must treat both fields as independently optional.

Implementation landed as: the 7 nullable fields on `KnowledgeNodeView`; a shared `_mastery_fold_inputs` (so `map_state`/`mastery_memory`/the self-assessed second fold read one input bundle); `_session_signals`, `_evidence_grant_times`, `_capstone_evidence` helpers in `app/cycle.py`; the TS mirror in `frontend/src/api/types.ts`; and `tests/app/test_knowledge_map_atlas_signals.py`. `map_state`, the fold's meaning, the overlay store, and every mutation route are untouched.

**Backend, spec/axiom-first. Lands first.**
- Amend `KnowledgeNodeView` (and `KnowledgeBranchView` where relevant) in `app/results.py` with the nullable signals (`sessions_total`, `sessions_done`, `next_session_at`, `evidence_label`, `evidence_confirmed_at`, `review_flagged`, `self_assessed`) per `02-…` Part B.
- Compute them in `app/cycle.py::knowledge_map_view` from data the service already holds (plan tasks for the node's `linked_module_ids`, telemetry confirmations, the mark-evidence record, the mastery fold's set-point vs derived distinction, the `08-…` review flag).
- No change to `map_state`, the fold's meaning, the overlay store, or any mutation route.
- Grow the TS mirrors in `api/types.ts` with the optional fields (so SA-B's `signals.ts` reads real fields, not speculative ones).
- **Tests (backend)**: each signal computed correctly and deterministically; nullable when the source is absent; a capstone carries no session fields; honest-count invariants unchanged; add invalid/edge fixtures where the pattern requires. `uv run make check` green.
- **Done when**: `GET /api/knowledge-map` returns the enriched view and the backend suite is green. Nothing user-visible changed yet (no frontend consumes the new fields until SA-C).

## SA-B — atlas foundation (pure functions + tokens)

**No rendering. Frontend pure logic + tokens.**
- Add the sky token block and the SVG `<defs>` gradient/clip set to `frontend/src/styles/tokens.css` (`01-…`), verbatim from the design page.
- New `frontend/src/lib/atlas/`:
  - `layout.ts` — `layoutSky(view, viewport)` (the deterministic **force-directed** layout engine, `02-…` Part A), including the demo-seeded region anchors, the deterministic body seeding, the fixed-iteration force simulation, the second-pass overlap policy, and the grid fallback.
  - `bodies.ts` — `bodyFor(node, tier, signals)`, `starFor(group)`, `beaconFor(branch)`, the brightness/warmth lerp, and the seeded-dust generator. Pure descriptors, no JSX.
  - `signals.ts` — the `NodeSignals` type + defensive readers over the SA-A fields on `KnowledgeNodeView`/`KnowledgeBranchView` (all optional, `02-…` Part B).
- Retire `lib/knowledgeMap.ts::tierTone` (or leave it, unused, until SA-C deletes its last caller — pick one and note it).
- **Tests (vitest)**: the full `02-…` layout suite (determinism + committed snapshot, composition fidelity, shape sweep, order stability, convergence bound, collapsed/open) + `bodyFor`/`starFor`/`beaconFor` mapping tables + brightness monotonicity + dust determinism.
- **Done when**: every atlas math function is unit-covered and the four gates pass; nothing user-visible changed yet.

## SA-C — desktop observatory

**Frontend.**
- New `components/Observatory.tsx` and its glyph children (`SkyChart`, `SkyPan`, `StarGlyph`, `PlanetGlyph`, `BeaconGlyph`, `CometGlyph`, `Nebulae`, `Ornaments`, `Tooltip`, `Overlay`), driven by `lib/atlas` (`03-…`).
- Wire it into `screens/Pathway.tsx` behind the responsive breakpoint (desktop branch); keep `Pathway`'s fetch/state/empty/version-mismatch logic.
- Pan/zoom focus glide, hover tooltip + dust parallax, open/close system state, click-to-select, the map-level add/create action row.
- Re-skin `NodeDrawer` to the atlas drawer (same dialog contract + actions; add the evidence card / review notice / self-assessed tick, each guarded by its signal).
- Retain the drawer's existing dialog accessibility (it already ships focus-trap + Esc + `role="dialog"` — free to keep). Full keyboard/SR treatment of the *chart bodies* is **not** built here; it is deferred to SA-F (decision C).
- **Tests**: extend vitest for any new pure helper; component render tests are not in the current toolchain (no jsdom/testing-library) — the browser assertion is the CDP smoke in SA-E. If light component tests are wanted, adding `@testing-library/react` + `jsdom` is a *new dependency* → ask first (README notes this).
- **Done when**: desktop `/pathway` renders the atlas from live data, every mutation works through the drawer, the four gates pass.

## SA-D — mobile atlas

**Frontend.**
- New `components/MobileSky.tsx` (scrolling sky, accordion `SystemCard`s, region/section headers, mission plaque) + the bottom-sheet variant of the drawer (`04-…`), reusing the shared mini-glyph SVGs and `lib/knowledgeMap.ts` helpers.
- The `matchMedia` breakpoint switch in `Pathway` so phones never run `layoutSky`.
- Touch-target, safe-area, contained-horizontal-scroll, no-hover, reduced-motion compliance (`04-…`).
- **Done when**: at a mobile viewport `/pathway` renders the scrolling sky, the sheet opens and every action works, the page never scrolls sideways, and the four gates pass.

## SA-E — ornaments, reduced motion, and the browser smoke

**Status: IMPLEMENTED** (four frontend gates green: `typecheck` / `lint` / `test` 308 / `build`).
Landed as: new pure helpers in `lib/atlas/render.ts` (`earliestNextSession`, `probeGeometry`, `bezelTicks`, `roseNodes`) with vitest coverage in `render.test.ts`; a new `components/atlas/Ornaments.tsx` (`InstrumentEdge` = bezel ticks + corner brackets + orrery, on the fixed instrument layer; `Probe` + `Bloom`, inside the pan group); their animations + the full reduced-motion audit in `tokens.css` (`atlas-spinr` / `atlas-drift` / `atlas-bloom`, `.probelab`, and the extended `prefers-reduced-motion` block now covering `orr1` / `orr2` / `drift` / `bloom` plus the mobile `km-drawer` sheet-slide); and the wiring in `Observatory.tsx` (bloom fires on a strict tier rise between fetches via a `prevTiers` ref, and is not mounted under reduced motion).

Two verification notes:
- **Browser smoke ran at both viewports** against the keyless demo server (`python -m agentic_calendar.app.web`) with the `ai-integration-engineer` pathway selected and a mixed sky seeded through the real `setpoint` route. Desktop (Observatory): verified nebulae/beacons/warm-vs-cool stars/honest counts, open-system orbit + all-honed constellation, ocean/rock worlds, mark-evidence → crown + proven drawer + evidence card, set-point down → honed count drops (7→6, plaque tracked), self-assessed tick, focus glide, and the orrery/brackets/ticks/plaque instrument edge. Mobile (MobileSky): the scrolling sky, region + capstone cards, accordion expand to mini-glyph member worlds + honest status lines, world tap → detail actions, and a custom-group create appearing under `YOUR ADDITIONS` as a comet.
- **The probe (`next_session_at`) is data-gated**: the demo env has no active-plan sessions, so the probe is honestly absent (graceful degradation) and its geometry is covered by `probeGeometry` unit tests rather than the live smoke. The **true bottom-sheet** (`max-width:560px`) could not be exercised through the automation surface (its render viewport is pinned wide, so `min-width:900px` was overridden to force MobileSky; the sheet CSS keys on ≤560px) — the sheet itself was browser-verified in SA-D and is unchanged here.

**Frontend + verification.**
- The ornament layer finished (mission plaque, orrery, bezel ticks, corner brackets, probe, constellation lines) and the one-shot tier-up bloom.
- **Reduced-motion implementation**: port the design page's `prefers-reduced-motion` fallbacks so every loop stills, one-shots resolve to end state, and transitions go instant — desktop and mobile. (Its dedicated CDP audit rides with SA-F; the implementation itself is nearly free and ships now.)
- **CDP smoke** (the project's reusable Chrome-DevTools harness): at desktop **and** mobile viewports, drive the real screen through select-pathway → open a system → open a world → set-point down (world leaves the honed count) → add a vocabulary node (appears in its system) → create a custom group + node (visible, counts unchanged) → mark evidence on a honed skill (world crowns). Assert the celestial state matches the honest data at each step. Every on-screen tier must be reproducible by `map_state` over stored data (the KT-D acceptance bar carries over). The smoke covers **functional + responsive** only; it does not assert keyboard/SR accessibility (decision C, → SA-F).
- **Done when**: the functional smoke passes at both viewports, reduced-motion is implemented, and the four gates are green.

## SA-F — accessibility (deferred follow-up)

**Status: IMPLEMENTED** (four frontend gates green: `typecheck` / `lint` / `test` 313 / `build`; the chart-body keyboard loop browser-verified end-to-end).
Was descoped from the initial build for cost (decision C) and tracked as documented debt; now landed.

Landed as:
- A shared **`SvgButton`** wrapper in `components/atlas/Glyphs.tsx` — `role="button"` + `tabIndex=0` + Enter/Space activation (`preventDefault` on Space so the page never scrolls) + an `aria-label`. Every interactive chart body in `Observatory.tsx` (capstone beacons, collapsed *and* open system stars, the collapse-✕, the delete-group affordance, and every world/comet) now renders through it, so all are Tab-reachable in document = reading order.
- Two pure, vitest-covered name composers in `lib/atlas/render.ts`: **`bodyAccessibleName`** (`${title}. ${statusLine(...)}` — the status line already puts tier + counts + flags in words, so what colour encodes is spoken) and **`systemAccessibleName`** (`"…, 2 of 5 honed, collapsed"`; personal groups read `"your group, n sketched"` and never a honed fraction). Covered in `render.test.ts`.
- **`:focus-visible` ring**: `.rim [role='button']:focus-visible` draws the gold dashed outline echoing `.selring`; keyboard-only, so a pointer click leaves no lingering ring. A matching dark-sky ring for the mobile native-button cards (`.m-cap/.m-srow/.m-card/.m-del:focus-visible`).
- **Drawer focus management** in `NodeDrawer.tsx` (the plan assumed this already shipped; it did not): on open, focus moves to the close button; Tab is trapped inside the dialog (wraps both directions); Escape closes; on close, focus returns to the invoking chart body. `aria-modal="true"` added. The mount-only effect uses an `onClose` ref so it never re-runs and steals focus mid-interaction across node switches.
- **Decorative layers hidden from AT** (`aria-hidden`): both dust layers, the nebula ellipses + per-system lamp glows + the overall light-pollution wash, the orbit ring / constellation, the vignette, and the duplicate visible label `<text>` (`.slab`/`.scount`/`.caplab`/`.plab`) — so the a11y tree is just the meaningful bodies plus the real-text plaque/counts. The `<svg role="group" aria-label="… — knowledge map">` names the instrument. (Mobile was already native-button accessible from SA-D; SA-F only adds its focus ring.)
- **Colour-independence**: verified — tier is conveyed by shape (rock/ocean/crown) + the spoken status line + the drawer ladder, never colour alone.

Verification (browser, keyless demo server, `ai-integration-engineer` with a mixed sky seeded through the real `setpoint` route):
- Tab from the toolbar reached the first SVG capstone with `:focus-visible` matching and the computed outline `rgb(232,192,122) dashed 2px` (`--star-gold`) — confirmed by zoomed screenshot.
- All 8 collapsed bodies exposed composed `aria-label`s (`"LLM Evaluation & Safety, 4 of 4 honed, collapsed"`, `"… Capstone — unproven"`); dust + duplicate labels `aria-hidden`.
- Enter on a system star expanded it (4 world buttons appeared, each `"… . Honed · self-assessed"` — honest, since seeded via set-point); Enter on a world opened the drawer (`role=dialog`, `aria-modal`, focus on the close button); Escape closed it and **returned focus to the invoking world button**; Tab / Shift+Tab wrapped within the drawer (real keys + dispatched, both directions).
- **Reduced-motion**: the loop/one-shot fallbacks shipped and were audited in SA-E; the OS `prefers-reduced-motion` flag could not be toggled through the automation surface (the same limitation SA-E noted for the bottom sheet), so its dedicated stillness sweep rests on the SA-E CSS audit + the existing `@media (prefers-reduced-motion: reduce)` block (unchanged here — focus outlines are not animations).

**Frontend-only** — no backend, spec, axiom, `map_state`, or mutation-contract change; SA-F touches rendering + accessibility affordances only.

## Test strategy (summary)

- **Pure logic → vitest.**
  The layout engine and the tier→body/star/beacon mappings are where the real complexity lives, and they are pure functions — so they carry the bulk of the automated coverage (SA-B), exactly the split the shipped `lib/knowledgeMap.test.ts` already models.
- **Backend signals → `make check`** (SA-A), deterministic per-field.
- **Real browser → CDP smoke** (SA-E functional + responsive; SA-F adds the a11y + reduced-motion assertions), because the current frontend toolchain has no component/DOM test layer and the atlas's correctness is ultimately "does the right star warm on the real screen."
- **No prompt-text or LLM assertions anywhere** — none of this touches an LLM surface; every assertion is over deterministic data.

## Definition of done (whole plan)

- `/pathway` renders the Star Atlas on desktop and mobile from live `KnowledgeMapView` data.
- Every KT-D capability (open/collapse, drawer/sheet, set-point up/down, mark-evidence, add vocabulary node, custom group/node CRUD, notes) works unchanged through the atlas.
- The map is honest (counts only, no invented data, degraded flourishes when a signal is absent) and quiet under reduced motion. Full chart-body accessibility (keyboard + SR) is the deferred SA-F bar, not SA-A…E's; the free pieces (real-text counts, shape-encoded tiers, accessible drawer/sheet) ship now.
- Layout is deterministic and unit-tested (snapshot-stable); the reference pathway echoes the hero composition; real 20–40-node maps render legibly and without overlap.
- Semantics in `narrative-pathways/06-…`/`08-…` are untouched; `map_state`, the overlay store, and every mutation contract are unchanged; SA-A's additions are purely additive read signals.
- All four frontend gates green per commit; `uv run make check` green on SA-A.

## Risk register

| Risk | Mitigation |
|---|---|
| Force-directed layout is non-deterministic / jitters between fetches. | Fixed seed positions + a fixed iteration count + no randomness (the environment bans `Math.random`/`Date.now`) + final rounding make it a pure function; a committed snapshot of the reference output is the regression guard (SA-B). |
| Layout looks cramped on odd real maps (e.g. 6 branches, dense groups). | Repulsion spreads dense regions; the SA-B shape-sweep asserts a legibility separation after relaxation; a deterministic second pass raises repulsion; a loud grid fallback beyond budget — never a scrambled sky. |
| A signal source is absent for some node (no scheduled session, no evidence yet). | The graceful-degradation contract (`02-…`) makes every signal nullable and every flourish optional; a missing signal removes its flourish and never fabricates one, so partial data always renders honestly. |
| SVG chart accessibility is deferred (decision C), leaving keyboard/SR gaps on the map bodies. | Accepted, documented debt tracked as SA-F, not a silent gap: the free pieces ship now (real-text counts, shape-encoded tiers, the accessible drawer/sheet, the mostly-real-DOM mobile path); SA-F completes the chart-body keyboard/SR work before production. |
| Motion overwhelms or violates reduced-motion. | Every loop/one-shot/transition has a reduced-motion no-op (carried from the design page), implemented in SA-E; the dedicated CDP stillness audit lands with SA-F. |
| Scope creep into backend mastery meaning. | Hard line: this plan changes only rendering + additive read signals. Any change to `map_state`/tiers/counts is out of scope and belongs to `06-…`/`08-…`. |
| Component-test gap (no jsdom today). | Pure logic is vitest-covered; the browser truth is the CDP smoke. Adding a DOM test layer is a new dependency — ask first, don't smuggle it in. |
