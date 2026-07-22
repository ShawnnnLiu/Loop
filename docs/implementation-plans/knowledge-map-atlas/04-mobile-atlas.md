# 04 · Mobile Atlas — The Scrolling Sky

Status: planning only.
Mobile is not a shrunk observatory.
The design page ships a distinct mobile treatment, and the product must too: on a phone the star chart becomes a **vertically scrolling sky** of accordion **system cards**, and the drawer becomes a **bottom sheet**.
Same honest counts, same four tiers, same mutation routes — a different, thumb-first layout.

## Why a separate treatment (not responsive shrink)

A 1180×665 SVG observatory with pan/zoom, hover tooltips, and 64px orbital blooms is unusable on a 390px-wide touch screen: bodies collide, hover doesn't exist, and pan/zoom fights the page scroll.
So the mobile path drops the layout engine entirely (`02-…`: `layoutSky` is desktop-only) and renders a DOM list.
The two share the same data (`KnowledgeMapView`), the same view-model helpers (`lib/knowledgeMap.ts`), and the same glyph SVGs (`StarGlyph`/`PlanetGlyph`/`BeaconGlyph`/`CometGlyph` rendered small, in a mini viewBox) — so a world looks like the same world on both, without a second rendering paradigm's worth of code.

## Structure (`MobileSky`)

A single scroll container with a subtle dark radial-gradient sky background and a faint static dust overlay (still under reduced motion):

```
MobileSky
├─ header counts (horizontally scrollable honest chips — worlds honed / proven / capstones)
├─ "Scroll the sky" hint (sticky, quiet)
└─ for each branch (evidence slot), in view order:
   ├─ region label (italic serif; lit when its capstone is proven)
   ├─ capstone card         // BeaconGlyph mini + title + "capstone proven/unproven"
   └─ for each group in the branch:
      SystemCard (accordion)
      ├─ header row: StarGlyph mini + title + honest count chip ("2/5 honed") + chevron
      └─ (expanded) member rows: PlanetGlyph/CometGlyph mini + title + honest status line
   ── "Core foundations" section for core groups ──
   ── "Your additions" section for personal groups (comets) ──
└─ mission plaque (name + honest totals) at the foot
```

Tapping a system row toggles the accordion (client state, no fetch).
Tapping a member row opens the **bottom sheet** for that node.
This mirrors the current DOM-accordion's information architecture exactly — it is that architecture, re-skinned to the dark sky — so the KT-D flows keep working with minimal churn.

## The bottom sheet (re-skinned drawer)

The sheet is the same node detail as the desktop drawer, same actions, same dialog contract, laid out for a phone:

- A grab handle, the tier ladder, the honest status line, the blurb.
- The note (inline), the confirmed-evidence card (proven; needs `evidence_label`, `02-…`), the review-flag notice (`review_flagged`), the self-assessed tick.
- Primary action by tier: `Schedule study` (discovered) · `Mark today's session done` (training) · `Mark evidence` (honed skill) · `Add refresher` (honed) — each hitting the same route as desktop.
- The adjust-mastery set-point control and, for custom nodes, delete.
- Slides up from the bottom; instant under reduced motion; Esc / backdrop-tap / grab-drag dismiss; focus-trapped `role="dialog"`.

## Responsive strategy (one screen, two renderers)

`Pathway` renders `Observatory` or `MobileSky` from a breakpoint, not two routes.

- Use a CSS/`matchMedia` breakpoint (proposed ~720px) as the switch; below it, `MobileSky`; at/above, `Observatory`.
- Prefer a `matchMedia` hook so the choice is reactive to rotation/resize and the heavy `layoutSky` never runs on phones.
- The page chrome (toolbar, header, count chips) is the shared responsive shell already in the SPA; only the chart body swaps.
- No fixed 1240/396 frames — those are design-artifact framings; the real screen is fluid between the breakpoints (the chart `<svg>` scales by `viewBox`; the mobile list is fluid width).

## Mobile-friendliness requirements (obsessed-with-pixels, per the engineering standard)

- **Touch targets** ≥ 44px for every system row, member row, chevron, sheet action, and the create/add affordances.
- **No hover-only affordance** — everything reachable by tap; the desktop tooltip has no mobile equivalent (the status line is inline on each row instead).
- **Horizontal scroll is contained** — the count chip strip scrolls inside its own overflow container; the page body never scrolls sideways (a project UI rule and a general one).
- **The sky background is dark but the page is light** — the sheet, the chrome, and the safe-area insets use the light tokens; only the scroll region is the observatory. Respect iOS safe-area (`env(safe-area-inset-*)`).
- **Momentum scroll** on the sky; the sticky "scroll the sky" hint fades appropriately; no scroll-latching or nested-scroll traps (a known past-gotcha on this project — verify in the CDP smoke).
- **Reduced motion**: the accordion expand, the sheet slide, and the dust all still; the training pulse stills; nothing loops.
- **Create/add on mobile**: the map-level "Add a skill / New group" actions live in an accessible action row (or a small `+` menu) above the list, and "New node" inside each expanded system — never hover-revealed.

## Accessibility

Because mobile is real DOM, most of this is accessible **almost for free**, so it ships in SA-D (unlike the desktop SVG chart, whose keyboard/SR work is deferred to SA-F, decision C). Keep the near-free wins:

- System rows and member rows are native `<button>`s with composed accessible names (title + honest status).
- The chevron state is conveyed via `aria-expanded`.
- Region and section labels are real headings, so a screen reader can navigate branch-by-branch.
- The sheet is a labelled, focus-trapped dialog returning focus to the row that opened it.
- Mini-glyph SVGs are `aria-hidden` (the row's text carries the meaning); tier is conveyed by the status line, not colour alone.

## Parity checklist with desktop

Same data, same routes, same semantics; only layout differs.
The CDP smoke (`05-…`) runs the core flow at both a desktop and a mobile viewport and asserts: a system opens, a world's sheet opens, a set-point-down drops the world out of the honed count, an added vocabulary node appears in its system, and a custom node/group is visible and counts nothing — identical assertions, two viewports.
