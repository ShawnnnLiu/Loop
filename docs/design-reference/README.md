# Design reference (read-only)

This folder is the **style axiom** for the hosted frontend — extracted verbatim
from `Admissions Agentic Scheduler.zip`. **Do not edit these files.**

Follow it for **style** (visual system, layout, state grammar, naming, the
deterministic-vs-AI framing), **not as a spec to copy verbatim** — the real
product diverges and changes will arise. When the design and the deterministic
backend disagree, the backend (contracts/axioms) wins; surface the mismatch.

## What's here
- `design-loop/` — **current source of truth** (hi-fi React/JSX prototypes):
  `onboarding.jsx`, `schedule.jsx` (the drag-review loop), `calendar.jsx`,
  `agent.jsx`, `accountability.jsx`, `generation.jsx`, `app.css`.
- `Loop - Star Atlas.html` — **visual source of truth for the Knowledge
  Map** (newest drop, 2026-07-19): the per-pathway mastery tree rendered as a
  "star atlas" (reference pathway: AI-Integration Engineer). Self-contained
  hi-fi page with node detail + ladder views. Semantics are normative in
  `docs/implementation-plans/narrative-pathways/06-knowledge-tree.md`; this
  page is normative for the visuals.
- `Loop - Pathway Map.html` — the previous Knowledge Map treatment (five
  tiers, hover lineage, detail drawer, desktop 1240 + mobile 396 frames);
  superseded by Star Atlas for visuals. `Loop - Pathway Map-print-4bewdj.html`
  is a print export of it.
- `claude_code_handoff/` — the designer's own handoff: `DESIGN-SYSTEM.md`,
  `DATA-MODEL.md`, `SPEC-*.md`, and `reference/` (jsx + `app.css`).
- `design/`, `v2/`, `*.html`, `landing/` — older / canvas / marketing variants.
- `report.docx`, `screenshots/` — supporting visual context.

## Current implemented frontend ≠ this design
The shipped hosted UI is minimal **server-rendered Jinja** (`backend/.../app/web/
templates/*.html` over `base.html`), not React. New read-only pages (#3, #4)
should match that minimal Jinja pattern while drawing visual cues from
`design-loop/`. Porting the full React system is a later, larger effort.
