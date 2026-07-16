# 01 · Product Design — The Story Layer

What the user sees and does, end to end. Contracts and increments live in the
sibling docs; this one fixes the product shape so those don't drift.

## The problem this solves

Recruiters and admissions readers evaluate **packages**, not activity lists. A
candidate with four unrelated projects loses to a candidate with three that
tell one story. The advice industry knows this ("have a spike", "tell a
coherent story") but delivers it as prose — nobody turns it into an execution
plan. This product's whole moat is turning intention into scheduled,
accountable execution; the story layer points that machinery at the highest
-leverage question the user has: *what should I build next so my record adds
up to something?*

Concretely, for the user this converts:

- "I should do more projects" → "your **AI-Integration Engineer** story has
  its model-serving pillar and its frontend-surface pillar empty; this plan
  schedules a project that fills the first one."
- "I volunteer at a shelter and code on weekends" (Tandem) → "those are two
  pillars of a community-technology story; here's the third."

## The three product objects

### 1. Character sheet ("who you are today")

A read-view over **confirmed** profile data — never a separate store:

- Evidence inventory: `experience` entries, each with a `kind` (work,
  project, volunteering, leadership, research, award, coursework) and
  `theme_tags` from a closed vocabulary. Both proposed by the intake node,
  both editable, both confirmed by the user in the existing review gate.
- Skills (taxonomy-normalized, as today), strengths, weaknesses.
- Nothing psychological. No "you are an achiever" typology. The sheet is what
  the user has *done*, structured. If the user's evidence is thin, the sheet
  is honestly thin — empty-over-fabrication carries over from the extraction
  contract.

### 2. Pathway cards ("stories you could build")

Curated `PathwayTemplate`s rendered as cards, deterministically ordered by
how many evidence slots the user's sheet already fills. Each card shows:

- **Spine** — the one-sentence claim the story makes ("Ships ML models into
  real products end-to-end").
- **Pillars** — the pathway's evidence slots, each marked filled / partial /
  empty for *this* user, with the user's own items shown under filled slots.
- **What this pathway is for** — the audience that buys this story (kinds of
  roles/teams; in Tandem, kinds of programs). Category language only; the
  target-company-categories rule (no names, no prestige tiers) applies to
  pathway copy verbatim.
- A short LLM-written fit note ("your billing-platform work and your two
  Python services already carry the backend-depth pillar") — explanation
  prose, generated from confirmed data, never the ranking mechanism.

Fit display is **"n of m pillars"**, never a percentage. Empty sheets get an
honest "0 of 6 — this would be a fresh start" card, not a hidden one: choosing
an aspirational pathway from zero is a legitimate move, and for a
college-freshman Tandem user it is the *normal* move.

### 3. Story progress ("how the package is coming together")

*(Two zoom levels share this data: the compact pillar panel below, and the
full **Knowledge Map** — the per-pathway tree with mastery tiers, speced in
`06-knowledge-tree.md`. The map is where the RPG visual language lives.)*

Once a pathway is selected, the Progress screen gains a **Story** panel:

- Pillars as progression tracks: **empty → in progress → filled**.
- *In progress* is deterministic: a syllabus module linked to the slot
  (`evidence_slot_id`) exists in the active plan.
- *Filled* requires an explicit user action — "mark evidence" with an
  optional artifact note/URL that becomes a new evidence item on the profile.
  Completing study tasks never auto-claims an artifact; having spent 12 hours
  on a project is not the same as having a project. This is the story-layer
  analog of the approval gate, and it is what keeps the progress bar honest.

## The flow

### Onboarding (wizard goes 4 → 5 steps)

`Goal → Time & constraints → Résumé & profile → `**`Your story`**` → Connect`

The **Your story** step renders after the résumé step (so extract/review has
usually populated the sheet, but manual-entry and skip users get the same
step over whatever they typed):

1. Character-sheet summary strip at top (evidence counts by kind, top themes).
2. Pathway cards for the resolved career track, ordered by filled-slot count.
3. User selects one card — or **skips**. Skip is first-class: no pathway is
   stored, every downstream surface behaves exactly as today. The feature
   must never make onboarding longer for a user who doesn't want it.
4. Selection previews consequences before confirm: "your plan will prioritize
   filling these 3 pillars."

### Living with a pathway

- Strategist proposals arrange modules around unfilled slots; each
  slot-linked module says so in its `reason` and carries the typed link.
- Week/Today screens are unchanged (tasks are tasks). The story layer is a
  planning-and-progress concern, not a calendar concern.
- **Change pathway** lives on the Tuning screen, mirroring how other
  plan-invalidating changes work: it warns that the syllabus regenerates,
  creates a new profile version, and re-runs the cycle. Evidence never
  resets — items are pathway-independent facts; only the slot mapping is
  recomputed against the new template.

### Re-assessment

Any evidence change (new item, "mark evidence", edit) deterministically
recomputes slot coverage on next view — no LLM in that loop, no background
jobs. The LLM fit note regenerates only on explicit user request
("refresh story summary"), keeping cost user-initiated.

## Gamification stance

Borrow the *structure* of games, not the aesthetics:

- **Class selection** = pathway choice: a real decision with visible
  build-consequences, reversible at a cost (replan), never auto-assigned.
- **Quest lines** = pillars: discrete, named, completable.
- **Progression** = slot states, driven by real artifacts.

Deliberately excluded: points, streak mechanics on story progress, levels,
comparative leaderboards, and any "rarity" framing of pathways. The
accountability layer already owns behavioral pressure (axiom 21, deterministic
and consent-gated); the story layer must not become a second, cuter pressure
system. One motivator per surface.

## Ethics line (this shapes copy and contracts)

The feature packages **what is true**; it must never manufacture what isn't:

- Pillars fill from confirmed evidence only; the "mark evidence" gate is
  user-explicit.
- Copy says "build your story" (do things), never "improve your story"
  (spin things). The product's answer to a gap is always *scheduled work
  that closes it* — that's the differentiator over essay-polish and
  résumé-keyword tools, and it's the same answer for a recruiter-facing user
  and a 16-year-old Tandem user.
- No prestige language anywhere in pathway content (registry review enforces
  the same denylist the extraction adapter uses).
- Tandem inherits this line hardened: essays grounded in confirmed evidence
  (see `05-tandem-vision.md`), because the temptation to fabricate is
  strongest exactly there.

## What this feature is NOT

- Not a personality test, archetype quiz, or "we detected your type" system.
- Not LLM-ranked: ordering, fit, gaps, and progression are deterministic.
- Not a segmentation of study content: modules still come from the
  Strategist under all existing validation; pathways *shape* proposals via
  typed constraints, they don't bypass anything.
- Not mandatory: skip-forever must remain a fully supported product state.
- Not a Tandem feature smuggled into Loop: Loop ships career pathways only.

## Related docs

- `02-contracts-and-registry.md` — every object above as a contract.
- `03-llm-surfaces.md` — the two propose surfaces and their bounds.
- `../../axioms/00-product-thesis.md` — thesis and "motivation is product
  state" (extended here to narrative).
- `../../axioms/21-accountability-layer.md` — the pressure system this layer
  must not duplicate.
