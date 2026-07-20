# Context-Window Splits — Calendar Grid Rework

Sizing companion to `00-overview.md`. Each split is **one fresh Claude Code
session ending in exactly one commit**, budgeted at roughly **300k total
session tokens** — reads, edits, test iterations, and gate runs included.

## Honest sizing: this is ONE split

Frontend-only, one screen plus two new pure lib modules and one
presentational component. Zero backend, contract, spec, or schema work. The
three features share the same file and the same geometry helpers; splitting
them would re-pay the fixed overhead for no benefit.

## Budget model (heuristic priors)

- **Fixed per-session overhead: ~50k.** CLAUDE.md + AGENTS.md + this folder
  + `ScheduleReview.tsx` (940 lines) + the grid section of `tokens.css` +
  `lib/datetime.ts`, `lib/stack.ts`, `lib/weekplan.ts` + `api/types.ts`
  skim, before the first edit.
- **G-A full-day grid: ~45k.** New `gridtime.ts` + tests, constant/clamp
  changes, shading bands, scroll effect.
- **G-B now indicator: ~15k.** One helper reuse, one interval change, two
  CSS classes.
- **G-C popover: ~55k.** Click-vs-drag wiring in the drag pipeline (the
  least predictable cost), new component + placement helper + tests, CSS.
- **G-D gates + smoke: ~30k.** Four npm gates (budget one failure-fix
  iteration) + dev-server browser smoke with seeded free/busy.
- **Total: ~195k** against the 300k budget. The slack is deliberate —
  overshoot (a session dying mid-commit) is the real failure mode.

## Overflow rule

One commit at the end, with one **internal fallback boundary**: after
G-A + G-B the grid is correct and honest on its own (titles still
ellipsized, no popover). If the session approaches budget mid-G-C, run the
G-D gates on what exists, commit at that boundary stating plainly that the
popover is not included, and resume in a fresh session with this kickoff
prompt plus "G-A/G-B are already committed; resume at G-C".

## The split

| Split | Phases | One-commit theme | Est. total | Gate |
| --- | --- | --- | --- | --- |
| 1 | G-A + G-B + G-C + G-D | Full-day scrollable grid, now line, block details popover | ~195k (50 + 45 + 15 + 55 + 30) | — |

## Conventions

- **Branch:** `calendar-grid-rework`, created from `main` once this plan
  folder has merged. If `docs/implementation-plans/calendar-grid-rework/`
  is missing from `main`, stop and ask.
- **One commit** at the end of the session (authorized by this prompt);
  never push.
- **Gates green before the commit:** `npm run typecheck && npm run lint &&
  npm run test && npm run build` from `frontend/`.
- `graphify update .` after code changes.
- **Reference drift:** line numbers were verified 2026-07-19 on the
  `user-plan-direction` working tree. If a cited line no longer matches,
  trust the named symbol over the line number and note the drift in the
  session summary.
- **Hard constraints (not to be relitigated):** frontend-only — nothing
  under `backend/`, `schemas/`, or `docs/specs/` changes and `make schemas`
  never runs; do not touch `Onboarding.tsx`, `lib/intake.ts`,
  `api/types.ts`, or `api/client.ts` (concurrent user-plan-direction
  surface); no new dependencies (no floating-ui — the placement helper is
  ~20 lines); busy blocks never show event names (axiom 06); no task
  `description` field is added — the popover slot stays null; drag
  semantics and server re-validation are untouched.

## Split 1 — G-A…G-D · Calendar grid rework — ~195k

**Primary docs:** `00-overview.md` (context + decisions + reference table),
then `01`–`04` in order.

Kickoff prompt:

```
Read docs/implementation-plans/calendar-grid-rework/00-overview.md and
SPLITS.md, then 01-full-day-grid.md, 02-now-indicator.md,
03-block-popover.md, 04-gates-and-smoke.md in that folder. Then read
frontend/src/screens/ScheduleReview.tsx, frontend/src/styles/tokens.css
(grid section ~600-770), frontend/src/lib/datetime.ts, lib/stack.ts,
lib/weekplan.ts, and skim frontend/src/api/types.ts (read-only). Create
branch calendar-grid-rework from main (stop and ask if the plan folder is
missing from main). Implement G-A through G-D as ONE commit per CLAUDE.md:
24h scrollable grid with off-hours shading and profile-derived drag clamp
(new lib/gridtime.ts + tests), Notion-style now line on today's column,
click-to-open BlockPopover with full title / times / honest status (new
component + lib/popover.ts + tests), fmtDur exported from lib/weekplan.ts.
Hard constraints: frontend-only (nothing under backend/, schemas/,
docs/specs/); do not touch Onboarding.tsx, lib/intake.ts, api/types.ts, or
api/client.ts; no new dependencies; busy blocks never show event names; no
description field — the popover slot stays null; drag semantics and server
re-validation untouched. Gates from frontend/: npm run typecheck && npm
run lint && npm run test && npm run build, then the 04 browser smoke via
the keyless dev server; run graphify update . after code changes. You may
commit at the end; do not push.
```
