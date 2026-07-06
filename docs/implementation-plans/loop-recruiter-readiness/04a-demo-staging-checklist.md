# 04a · Demo Video — Staging Checklist (agent-prepared)

Companion to `04-demo-video.md`. Everything here is derived from the code and
tests on this branch (2026-07-05); re-verify against the deployed version on
recording day. The recording itself, narration, and account setup are user
actions; the embed + captions + poster land as a follow-up commit once the
footage exists (embedding before then would ship a broken `<video>`).

## Preconditions (record only when ALL are true)

- [ ] `ux-quality-pass` is merged **and deployed** — it is merged to `main`
      (PR #21); confirm the deploy, or B1/B2 recovery screens won't exist on
      camera.
- [ ] The `02` domain cutover is done (the outro shows the URL — record on the
      real domain, not `acme-agentic-cal.fly.dev`).
- [ ] Increment 01 + 03 are deployed (the hero and "How it's built" nav link
      appear in the opening shot).
- [ ] Dedicated tester Google account with a realistic-but-fake busy calendar;
      account email cropped or a demo address on screen.

## Staging the failure beat — option (a), replan (recommended)

The replan surface is deterministic; the exact trigger chain, from
`CycleService._replan_decision` (`backend/src/agentic_calendar/app/cycle.py`)
and `tests/app/test_replan_surfacing.py`:

1. **Onboard with a motivation profile** and set the recovery preference to
   **ask each time** (`recovery_mode_preference = ask_each_time`). This is
   what makes the recovery-mode **picker** appear on camera instead of a
   silently pre-resolved mode — the picker is the "engineers lean in" shot.
2. **Approve and write a week**, so a plan is ACTIVE with scheduled sessions.
3. **Check in with at least one session marked missed.** With a motivation
   profile on file, the accountability engine's
   `GENERATE_RECOVERY_PLAN_DRAFT` decision drives the replan verdict — a
   single missed session is enough (pinned by
   `test_status_surfaces_pending_recovery_choice_until_mode_supplied`).
4. **Visit the Week screen**: the "needs attention" chip → replan banner →
   recovery-mode picker (rollback of scope / reschedule choices) → choose one
   → re-approve the visibly minimal diff. That whole arc is the 0:45–1:05 beat.

Fallback trigger if the accountability path is quiet on the deployed build:
**capacity mismatch** — completion ratio below **0.60** for **2 consecutive
weekly cycles** (`drift/thresholds.py: capacity_completion_floor = 0.60,
capacity_min_cycles = 2`) maps to REDUCE_WEEKLY_LOAD → a scope-reduction
recovery replan. Slower to stage (two check-in cycles) but threshold-exact.

## Staging option (b), write failure — only if (a) is rejected

Not safely stageable against real Google. Record separately against the
keyless dev server (`uv run python -m agentic_calendar.app.web`) and splice:
the fake adapter (`calendar_writer/in_memory_adapter.py`) supports
`FailureModes` (used throughout `tests/web/test_calendar_write.py`), but the
dev composition root does not currently expose a failure toggle — forcing it
needs a small, uncommitted local edit. The dev server serves the same SPA, so
footage is visually identical. Recommendation stands: prefer (a).

## Shot-by-shot staging notes (beat sheet in `04-demo-video.md`)

- 0:10–0:25 onboarding: pre-write the goal/hours/windows text to paste — no
  typing pauses on camera; résumé paste optional (use obviously synthetic
  content if shown).
- 0:25–0:45 review/approve: stage the drag so the moved block visibly
  re-checks (server round-trip); linger one beat on the hash line of the
  approval screen; have Google Calendar already open in the next tab.
- Outro: the thesis line is on the landing page; end on the real URL.

## Embed spec (implement AFTER footage exists — follow-up commit)

- H.264 MP4, 1080p, target ≤ 15–20 MB for ~90 s.
- Self-hosted next to the landing (the Dockerfile already COPYes `landing/`);
  **no YouTube iframe** — it would contradict the no-tracking trust item one
  scroll above.
- `<video controls preload="metadata" poster=…>` with a hero-mock frame as
  poster; WebVTT `<track kind="captions">` (recruiters watch muted).
- Responsive check: must not break the `@media (max-width: 820px)`
  single-column layout.
