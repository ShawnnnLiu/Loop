# Tandem 同舟 — Implementation Handoff

A complete, self-sufficient package for a developer (or a Claude Code agent) to implement this product in a real codebase. You do **not** need the conversation that produced it — everything is here.

> **Read order:** this file → `DATA-MODEL.md` (the backend contract) → the three `SPEC-*.md` flow specs → `DESIGN-SYSTEM.md`. Keep `reference/preview.html` open in a browser as the visual source of truth while you build.

---

## What this is

**Tandem 同舟** ("same boat") is an **agentic scheduler for college applicants** — a high-school student (our reference user is Maya Chen, Class of 2027, pre-med) tells it a goal and a deadline; it back-plans the milestones (essays, tests, recommender asks, supplements) and writes the weekly study/prep blocks to **Google Calendar**. An always-docked agent proposes the plan; the student approves it.

It is **not** a calendar app. Google Calendar owns scheduling and is the system of record for time. Tandem owns *planning, milestones, proposals, and telemetry* and writes accepted blocks into gcal.

## The one idea that governs the whole build

> **The model proposes. Deterministic infrastructure disposes.**

Every capability is in exactly one of two columns, and the boundary is load-bearing — it's the product's trust story, not an implementation detail. The `CapabilityMap` screen (`reference`, screen 7) renders this split verbatim; build to it.

| AI · proposes (must be approved) | Deterministic · acts (no model in the loop) |
|---|---|
| Parse transcript / activity files → structured fields | Accept & schedule → write block to Google Calendar (idempotent, retry-safe) |
| Generate syllabus / milestone tree | Mark done → log completion + actual duration |
| Regenerate week | Drift detection (rule-based: missed % + reschedule count) |
| Recovery plan (writes *how*, not *if*) | Calendar sync (pull busy windows, respect quiet hours) |
| Explain "why this block" | Permission gate (sponsor/parent visibility, per-field consent) |
| Weekly reflection | Cost & retry caps (bounded budget, concurrency lock) |

**Hard rules that fall out of this — enforce them server-side, not just in the UI:**
1. **No model output causes a side effect without an explicit user `✓`.** Parsing, syllabus, week regen, recovery all land in an **approval gate** first.
2. **The agent never writes to the calendar without an explicit accept.** Every accept has a **60-second undo**.
3. **AI reads, the user confirms.** Parsed fields are shown for review and are editable; nothing is persisted to the profile until "Confirm & continue."
4. **Deterministic steps never call the model** — they validate and store. Don't "helpfully" route a plain form field through an LLM.
5. **File privacy:** uploaded transcripts/activity files are scoped to the user, never shared cross-tenant, and **never used for training**. Deletable any time. (This is stated in the UI; honor it in storage + pipelines.)

## The three flows (and their screens)

1. **Onboarding** (`SPEC-onboarding.md`) — a linear 7-step first-run wizard. Steps 1–3, 5, 7 are deterministic forms; steps 4 (transcript) and 6 (activities) are the **two AI parse steps**. Resumable at any step. Reference screens: Deadline, Transcript parse, Courses, Activities parse.
2. **Calendar** (`SPEC-calendar.md`) — the main app screen. Week grid of day-columns + an expanded day rail for the selected day + a milestone track across the top. The **block state grammar** (proposed / accepted / done / locked / rest) is the core data concept.
3. **Agent** (`SPEC-agent.md`) — a docked right rail: pending approvals → conversation thread (with visible tool-call rows) → composer + slash commands + trust strip. Plus the capability map.

## Fidelity & how to treat the reference files

These are **hi-fi designs** — the visuals, copy, spacing, and states are intentional and final-ish. But they are **React-in-the-browser prototypes (Babel, `window.*` globals), not production code.** Do **not** ship the `.jsx`/`.css` as-is.

- **Reproduce:** layout, information hierarchy, copy, state grammar, the AI/deterministic boundary, the interaction model (approval gate, undo, review-before-commit).
- **Re-implement in your stack:** component structure, routing, data fetching, real form controls, real Google Calendar integration. If the codebase already has a design system, **map the tokens** in `DESIGN-SYSTEM.md` onto it rather than porting `app.css` literally.
- **Static placeholders to replace with real state:** all data in the mocks is one hard-coded fixture (Maya Chen, Jul 6–12 week). Selected cards, "✓ read" chips, parsed values, "synced 2m ago" — all need real backing.

## Suggested build order

1. **Data model + persistence** (`DATA-MODEL.md`) — `User`, `OnboardingState`, `Milestone`, `Task`/block, `Proposal`, `FileUpload`, `CalendarLink`. Get the block **state machine** right first; everything renders off it.
2. **Deterministic core** — onboarding form steps, accept→gcal write, mark-done telemetry, drift rules, calendar sync. No model yet. This alone is a usable product skeleton.
3. **Google Calendar integration** — OAuth, push accepted blocks, pull busy/locked windows, 60-second undo, idempotent writes.
4. **AI layer behind the gate** — the two onboarding parse calls, then syllabus generation, week regen, recovery, explain, reflection. Each returns a **Proposal** that the UI must approve before it commits.
5. **Agent surface** — wire the dock to proposals + thread + tool-call log + slash commands.

## File map of this package

```
claude_code_handoff/
├── README.md            ← you are here (overview + the governing idea + build order)
├── DATA-MODEL.md        ← entities, state machines, and the HTTP API contract (start here for backend)
├── SPEC-onboarding.md   ← 7-step wizard, the two AI parse steps, per-screen breakdown
├── SPEC-calendar.md     ← week grid + day rail + milestones, block state grammar
├── SPEC-agent.md        ← docked rail, approvals/thread/composer, capability map
├── DESIGN-SYSTEM.md     ← tokens, type scale, state colors, component classes
└── reference/
    ├── preview.html     ← OPEN THIS — all 7 screens at 1440×900, the visual source of truth
    ├── onboarding.jsx   ← real design source (4 onboarding screens)
    ├── calendar.jsx     ← real design source (calendar screen + shared topbar/milestones)
    ├── agent.jsx        ← real design source (agent dock + capability map)
    └── app.css          ← design tokens + component styles (the literal CSS source)
```

The original full design canvas lives at the project root as `Designs.html` (all screens, pan/zoom, focus mode) if you want to explore them in context.
