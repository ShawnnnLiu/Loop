# Design reference (read-only)

This folder is the **style axiom** for the hosted frontend — extracted verbatim
from the `Admissions Agentic Scheduler*.zip` design drops (latest: drop 3,
2026-07-20). **Do not edit these files.**

Follow it for **style** (visual system, layout, state grammar, naming, the
deterministic-vs-AI framing), **not as a spec to copy verbatim** — the real
product diverges and changes will arise. When the design and the deterministic
backend disagree, the backend (contracts/axioms) wins; surface the mismatch.

## What's here
- `uploads/loop-landing-handoff/` — **animated landing-page handoff**
  (newest drop, 2026-07-20): `HANDOFF.md` (the task brief and its hard
  constraints), `landing/index.html` (the finished scroll-animated Loop
  landing page — the file meant to replace the live `landing/index.html`),
  `landing/how-its-built.html` (tone reference, identical to the live page),
  and read-only `frontend/`/`backend/` snapshots of the repo source each
  animation scene was modeled on. Adoption plan:
  `docs/implementation-plans/animated-landing/README.md`.
- `design-loop/` — **current source of truth** (hi-fi React/JSX prototypes):
  `onboarding.jsx`, `schedule.jsx` (the drag-review loop), `calendar.jsx`,
  `agent.jsx`, `accountability.jsx`, `generation.jsx`, `app.css`.
- `Loop - Star Atlas.html` — **visual source of truth for the Knowledge
  Map** (updated in the 2026-07-20 drop: the "YOUR ADDITIONS" header now
  hides while the side panel is open): the per-pathway mastery tree rendered
  as a "star atlas" (reference pathway: AI-Integration Engineer).
  Self-contained hi-fi page with node detail + ladder views. Semantics are
  normative in
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

## Current implemented frontend vs this design
The shipped hosted UI is the Vite React SPA in `frontend/`; its global
stylesheet `frontend/src/styles/tokens.css` was ported from
`design-loop/app.css`, so the SPA already follows this design system.
The live marketing site is the static `landing/*.html` set served by the
backend at `/`, `/how-its-built`, `/privacy`, `/terms`.
When the design and the deterministic backend disagree, the backend
(contracts/axioms) wins; surface the mismatch.
