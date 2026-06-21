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
- `claude_code_handoff/` — the designer's own handoff: `DESIGN-SYSTEM.md`,
  `DATA-MODEL.md`, `SPEC-*.md`, and `reference/` (jsx + `app.css`).
- `design/`, `v2/`, `*.html`, `landing/` — older / canvas / marketing variants.
- `report.docx`, `screenshots/` — supporting visual context.

## Current implemented frontend ≠ this design
The shipped hosted UI is minimal **server-rendered Jinja** (`backend/.../app/web/
templates/*.html` over `base.html`), not React. New read-only pages (#3, #4)
should match that minimal Jinja pattern while drawing visual cues from
`design-loop/`. Porting the full React system is a later, larger effort.
