# G-D — Gates and Smoke

## Gates (all from `frontend/`)

```bash
npm run typecheck
npm run lint
npm run test
npm run build
```

Backend is untouched by this plan — `make check` is not required (running
it is harmless but proves nothing new), and `make schemas` must NOT run (no
contract change). After code changes: `graphify update .` from the repo
root.

## Real-browser smoke (keyless dev server)

The dev server serves the built SPA without Google credentials:

```bash
cd frontend && npm run build
cd ../backend && uv run python -m agentic_calendar.app.web
```

Use the Chrome DevTools/CDP harness if available in the session, else a
manual pass. Dev mode returns `free_busy: []` (no per-user token,
`routes_cycle.py:200-210`), so for the busy-block checks seed the draft via
the dev propose path with an explicit `free_busy` body including one 6–7am
interval and one 23:00–01:00 interval — the dev-mode propose honors a
client-supplied list precisely for this kind of testing
(`routes_cycle.py:173-178`).

Checklist:

1. Grid opens scrolled to the working window (not midnight); all 24 hour
   labels reachable by scrolling; day header stays sticky.
2. The 6–7am busy block is visible in the right column; the 23:00–01:00
   interval renders as two segments (23–24 and 0–1 next day).
3. Off-hours bands are tinted; the allowed window is not.
4. Now line sits at the current wall-clock time on today's column; absent
   after paging →; back ← restores it.
5. Drag a proposed block: still snaps to 15min, still clamped to the
   allowed window, server rejection still snaps back with the typed reason
   banner. Drag across the now line works (no pointer interception).
6. Click (no movement) opens the popover with the full title; Escape,
   backdrop, and week-paging each close it; a block in the last column
   opens leftward.
7. Busy-block popover shows the privacy copy and no event name.
8. Plan view toggle still renders and returning to Grid does not re-scroll.

## Wrap-up checklist

- All gates green; smoke checklist done (note any CDP-vs-manual choice).
- No file outside the allowed list in `00-overview.md` was modified
  (`git status` review — remember the concurrent user-plan-direction
  session may have its own uncommitted files; never revert or stage them).
- One commit on `calendar-grid-rework` per the split convention; do not
  push.
