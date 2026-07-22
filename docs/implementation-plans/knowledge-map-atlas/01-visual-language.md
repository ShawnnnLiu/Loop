# 01 · Visual Language — The Observatory

Status: planning only.
This doc makes the `Loop - Star Atlas.html` metaphor precise enough to implement, and states which parts are **normative** (semantics inherited from `narrative-pathways/06-…`) versus **stylistic** (the atlas's own visual grammar).
Read the design page alongside it; where a pixel detail is unstated here, the page is the source of truth for style.

## The frame — a dark instrument in a light page

Loop's page chrome stays exactly as it is today: paper toolbar, ink brand, the `Today · Schedule · Pathway · Check-ins` nav, the sync pill, the pathway header with its serif name and italic tagline, the honest count chips.
The map itself is the one dark surface: a **bezel** (brushed-metal gradient) holding a **rim** (brass-edged, vignetted) that contains the **sky** (a radial near-black gradient).
This is deliberate and is the plan's theme rule: the app has no dark mode and this plan adds none; the observatory is dark because an observatory is dark, not because the app switched themes.
Everything outside the rim uses the existing light tokens; everything inside uses the new sky tokens (below).

## New design tokens

`frontend/src/styles/tokens.css` already has the light palette the page chrome needs (`--ink`, `--paper*`, `--clay*`, `--sage*`, `--gold*`, `--line*`, fonts, radii, shadows).
The sky needs a new block, ported verbatim from the design page's `:root` (add to `tokens.css`, do not invent values):

```css
--sky:#0b1420; --sky-2:#142333;
--chalk:#cfdae2; --chalk-dim:#8ea1b5;
--star-gold:#e8c07a; --magma:#e0764a; --ocean:#3f8f88;
--brass:#8a6f3f; --brass-dim:rgba(138,111,63,.45);
```

Plus the SVG `<defs>` gradient set from the page (`g-sky`, `g-vig`, `g-rock`, `g-ocean`, `g-haze`, `g-glow`, `g-glowc`, `g-lamp`, `g-corona`, `g-ember`, and the four `g-neb-*` nebula fills) and the `clip-p14` planet clip.
These live once in a shared `<svg width="0" height="0">` defs block the desktop chart references (SA-B).
No token is renamed; the existing `--gold` and the new `--star-gold` coexist (the page uses both — `--gold` for the light chrome, `--star-gold` for lit stars).

## The tier → celestial-body mapping (normative)

The four tiers are unchanged from `06-…`; only their rendering is restated here.
This table replaces `lib/knowledgeMap.ts::tierTone` (the old fill/ring gilding ramp).
It is a pure function `bodyFor(node, tier, signals) → BodyDescriptor` in `lib/atlas/` (SA-B), unit-tested, driving the SVG declaratively.

| Tier | World (skill/added-skill node) | Meaning (unchanged) |
|---|---|---|
| `discovered` | Barren cratered **rock** (`g-rock` fill), dashed chalk outline, faint chalk glow. | On the map, no study yet. Nothing is blocked. |
| `training` | Rock with **magma cracks** (`--magma`), a soft **ember pulse** halo, and — when session data is present — an **orbital trail** of arc segments (one per planned session, filled for sessions done). | Study scheduled or under way. |
| `honed` | A living **ocean world** (`g-ocean`: green-teal continents, faint cloud bands). | The planned study minutes are complete, or the user marked it done. |
| `proven` | Ocean world **crowned**: a tilted **ring**, a `✓` badge, a warm glow, and a lit hemisphere of star-flecks. | Honed, plus a real artifact the user confirmed. |

Notes that are normative, not decorative:

- **Honed is the count threshold.** A world counts toward its group's and branch's honed tally at `honed` and above — identical to `isMastered` (`proven ⊃ honed`).
  The ocean is the visual "this counts."
- **Proven is always user-gated.** The crown appears only when evidence is confirmed; it is never automatic.
- **Self-assessed honesty.** When a node's tier came from a `MasterySetPoint` rather than derived study (the `self_assessed` signal, `02-…`), the world renders identically but its drawer carries a quiet "self-assessed" tick.
  No shaming badge on the map — the honest label lives in the drawer, per `06-…`.
- **Review flag.** A review-flagged node (`06-…`/`08-…`; the `review_flagged` signal) carries a slow **shimmer** dashed ring — "the minutes are done but your own check-ins were shaky; still honed, worth a second look."
  It never lowers the tier.

## Star systems (groups)

A group is a **star**, not a planet; it has no tier of its own.
Its brightness and warmth are a pure function of its honest honed fraction `k = honed_count / total_count` (`starFor(group) → StarDescriptor`, SA-B):

- Colour lerps from cool chalk-white (`k = 0`) to warm star-gold (`k = 1`); radius grows with `k`; a glow and cross-flare scale with `k`.
- Any member in `training` adds an ember pulse to the star (the system is "active").
- Collapsed, the star's label shows the honest count chip — `"Retrieval & Grounding · 2/5 honed"` — never an average or percentage.
- When **every** member is honed, expanding the system draws a one-shot **constellation** — a gold polygon linking its worlds — the "system complete" flourish.
- A **core** group (serves 2+ slots) is a star like any other, placed in the shared centre region (`02-…`).
- A **personal / custom** group's star is chalk-dashed and never warms — it joins no count.

## Capstone beacons

One capstone per evidence slot, branch-level, no group — exactly `06-…`.
It renders as a **beacon** at its region's head (`beaconFor(branch) → BeaconDescriptor`):

- **Unproven**: a caged ember — a dashed rotated square around a dim core, with an ember pulse.
  Label: `CAPSTONE — UNPROVEN`.
- **Proven**: a **supernova** — a rayed corona (`g-corona`), radiating spokes, a white-hot core.
  Label: `CAPSTONE ✦ PROVEN`.
- Its state is slot coverage, not study minutes: a capstone has no `expected_minutes` and no session trail; its drawer says "this capstone *is* the branch's real artifact; it turns Proven the moment you confirm it exists — never automatically."

## Nebula regions and mastery light-pollution

Each non-core branch is a faint elliptical **nebula** (`g-neb-clay/teal/gold/sage`) with an italic serif region label.
As the branch masters, the sky brightens honestly:

- Each honed-heavy system casts a soft **lamp glow** (`g-lamp`) scaled by its `k`.
- A branch whose capstone is proven lights its whole nebula.
- Once more than half of all pathway worlds are honed, a gentle overall light-pollution wash lifts the sky — the "flourishing" end state.

All of this is derived from the same honest counts; there is no separate "progress" number anywhere.

## The personal layer — comets

Custom groups and custom nodes are the personal layer (`06-…`): they never count, never enter prompts, cap at `honed`.
On the sky they read as **comets** — chalk-sketched circles with a short dashed tail, never the ocean-green or gold ramp — grouped under a quiet `YOUR ADDITIONS` header set apart from the pathway regions.
A comet can warm slightly (a teal core at honed) but never gilds and never joins a constellation or a count chip.
This is the "one map without lying about what counts" rule made visual.

## Ornaments (the instrument dressing)

Stylistic, not semantic; all respect reduced motion.
Implement them as a static ornament layer so they never interfere with hit-testing:

- **Mission plaque** — a cartouche (bottom-left) engraving the pathway name and the honest totals: `4 branches · 8 systems · N worlds · 3 capstones`, then `n honed · n proven · n of 3 capstones proven`.
  This is the accessible textual truth of the whole map; it is also what a sponsor surface may show (branch counts only, `06-…`).
- **Probe** — a small drifting craft heading toward the next scheduled session's world, with a `next session · <when>` label (needs `next_session_at`, `02-…`; omitted entirely when null).
- **Orrery** — a decorative armillary in the corner; pure ornament.
- **Bezel ticks + corner brackets** — engraved instrument edge; drawn on the rim, never zoomed with the sky.
- **Seeded star dust** — two parallax layers of faint stars (deterministic RNG seed, so the sky is stable across renders); parallax follows the pointer on desktop, still on mobile and under reduced motion.

## Motion and reduced motion

Every animation in the design page has a `prefers-reduced-motion: reduce` fallback, and this plan keeps that contract strictly:

- **Loops** (twinkle, ember pulse, review shimmer, orrery/trail spin, probe drift, dust) all **stop** under reduced motion, resolving to a calm static opacity.
- **One-shots** (the supernova **bloom** on a tier-up, the constellation fade-in) do **not** play under reduced motion; the end state renders immediately.
- **Transitions** (drawer/sheet slide, chevrons, the sky pan/zoom focus, dust parallax) become instant under reduced motion.
- The one motion that fires on user action — a brief fill/bloom when a node changes tier while the view is open — is the only "reward" animation, and it too no-ops under reduced motion.

Reduced motion is *implemented* in SA-E (porting the design page's fallbacks); its dedicated audit — with the OS flag set, nothing on the screen may move — is verified with the deferred SA-F accessibility pass (decision C).

## Accessibility (the SA-F spec — deferred, not dropped)

> **Deferred to SA-F (decision C, 2026-07-21).** Full keyboard/screen-reader treatment of the SVG chart bodies is descoped from the initial build (SA-A…E) for cost, and tracked as the documented follow-up SA-F (`05-…`). The section below is that follow-up's target spec. What ships *now* is the cheap/free subset: the real-text honest counts, the existing drawer/sheet dialog semantics, and colour-never-the-only-signal (tier is also shape). The rest — focusable chart bodies, keyboard traversal, chart-body focus management — lands in SA-F before the atlas is production-complete.

An SVG star map is inaccessible by default; this plan will not ship one *as final*.
Requirements, owned across SA-C/SA-D/SA-E:

- **The honest counts are the accessible truth.**
  The mission plaque, the per-branch header chips, and each system's count chip are real text (or `aria-label`ed), so a screen reader hears "Retrieval and Grounding, two of five honed" — the same fact the star's colour encodes.
- **Every interactive celestial body is a real control.**
  Systems and worlds are `role="button"` (or native `<button>` wrappers) with an accessible name = title + status line + tier, `tabindex` in reading order, operable by Enter/Space, with a visible focus ring (the existing `.selring` doubles as focus affordance).
- **Keyboard traversal.**
  Tab reaches every capstone, system, and — when a system is open — its worlds; arrow-key roving within a system is a nice-to-have, Tab order is the floor.
- **The drawer/sheet is a proper dialog** (`role="dialog"`, labelled, focus-trapped, Esc-closable) — the current `NodeDrawer` already does this; keep it.
- **Colour is never the only signal.**
  Tier is also conveyed by shape (rock vs ocean vs crowned) and by the drawer's ladder and text, so the map is legible to colour-blind users and in the tooltip/plaque text.
- **Decorative layers are hidden from AT** (`aria-hidden` on dust, orrery, bezel, nebulae) so the accessibility tree is just the meaningful bodies plus the textual counts.

## What is deliberately absent (unchanged from `06-…`)

No XP, no levels, no percentile ranks, no decay timers, no letter grades, no LLM judgment of quality, and no edges or locks anywhere.
The sky warms with honest study and cools only by an explicit user set-point.
The system never renders a competence it cannot observe.
