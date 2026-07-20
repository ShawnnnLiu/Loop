# 04 · Demo Video

The only way a cold visitor experiences the product through an allowlist.
Embedded above the fold next to (or replacing) the static week mock. Screen
recording + captions; clarity and pace over polish.

## Sequencing (refined — record after the UX pass ships)

Record **after** the `ux-quality-pass` branch (and ideally the D-track prose
upgrades) is merged and deployed, and after the `02` domain cutover:

- The recovery beat the draft wanted (the "engineers lean in" moment) only
  exists on that branch: B1's 3-option write-failure recovery and B2's
  replan banner + recovery-mode picker.
- D2's voice rewrite improves every sentence visible on screen.
- The outro shows the URL — record it on the real domain, not
  `acme-agentic-cal.fly.dev`.

## Beat sheet (draft's timing, mapped to real screens)

| Time | Beat | What's actually on screen |
| --- | --- | --- |
| 0:00–0:10 | Hook | Landing hero; voiceover: "Loop turns a career goal into a study plan on your real calendar — and never touches your calendar without your approval." |
| 0:10–0:25 | Setup | Onboarding form (goal, weekly hours, deep-work windows, résumé paste), then the Generation screen doing its work. |
| 0:25–0:45 | Review & approve | Week view: drag a proposed block (server re-check visible), then Approval — linger one beat on the hash line — approve, then cut to Google Calendar with the events landed. |
| 0:45–1:05 | Failure handled well | Either (a) B2 replan: a drifted week surfaces the "needs attention" chip → banner → recovery-mode picker → re-approve a visibly minimal diff, or (b) B1 write failure: the 3-option rollback/retry/keep screen. |
| 1:05–1:20 | Close | The thesis line over the landing page; one sentence on tests + eval-gated prompts; the URL. |

## Staging the failure beat (the only hard part)

- **Replan (option a) is stageable on the real deployment**: check in a week
  with enough missed/short sessions to cross the drift thresholds, then show
  the replan surface. Deterministic thresholds make this reproducible —
  derive the exact check-in pattern from the drift classifier tests.
- **Write failure (option b) is not safely stageable against real Google.**
  If (b) is preferred, record that beat separately against the keyless dev
  server (`uv run python -m agentic_calendar.app.web`), forcing the fake
  calendar adapter to fail verification, and splice it in. The dev server
  serves the same SPA, so the footage is visually identical.
- Recommendation: (a) — one continuous real recording beats a splice.

Use a dedicated tester Google account with a realistic-but-fake busy
calendar. No real personal data on screen; check the account email is
cropped or a demo address.

## Hosting decision

Self-host the file — do not embed YouTube:

- The trust story includes "no tracking"; a YouTube iframe injects Google
  cookies/requests (even `youtube-nocookie` phones home on play). It would
  contradict the page one scroll above it.
- Mechanics: H.264 MP4, 1080p, target ≤ 15–20 MB for ~90s (screen content
  compresses well), `<video controls preload="metadata" poster=…>` with the
  existing static mock (or a frame of it) as the poster. Serve it like the
  landing file (a static route next to `app.py:160-164`, or a `landing/`
  sibling asset — note the Dockerfile already COPYes `landing/`).
- Fly bandwidth at ≤100 testers + recruiter traffic is negligible.
- Add captions (`<track kind="captions">` WebVTT) — recruiters watch muted.

## Division of labor

The user records narration/screen (agent can't). The agent's commits:
staging script/checklist for the drift scenario, the poster frame, the
`<video>` embed + captions file, the responsive check (video must not break
the 820px single-column layout).

## Acceptance criteria

- A muted, cold visitor understands propose → review → approve → write and
  sees one failure handled gracefully, in ≤ 90 seconds, with zero sign-in.
- Everything shown is shipped behavior on the deployed version (same honesty
  rule as `01`).
- Page weight stays reasonable: video lazy-loads (`preload="metadata"`),
  poster renders instantly.
