# Loop Recruiter Readiness — Landing Surface Pass

Status: **complete** — merged to `main`; the remaining items are user/ops
actions tracked in `REMAINING.md`. Per increment:

- `01` **DONE** — false rollback claims fixed, footer byline added (GitHub
  profile link; portfolio URL still pending from the user).
- `02` **agent side DONE** — `CANONICAL_HOST` 301 redirect (env-driven no-op
  until set) + fly.toml cutover notes + tests. Pending user infra: buy
  domain, `fly certs add` + DNS, Google OAuth console updates, flip
  `OAUTH_REDIRECT_URI`/`CANONICAL_HOST`, deploy + verify.
- `03` **DONE** — `landing/how-its-built.html` + `/how-its-built` route (both
  composition roots + Dockerfile env), landing nav/footer links, tests;
  numbers re-measured at ship time (see the increment-03 commit message).
- `04` **staging prep DONE** (`04a-demo-staging-checklist.md`); recording is
  a user action gated on deploy + domain cutover; embed/captions/poster land
  after footage exists.
- `05` still deferred (entry criteria unchanged).

Provenance: refined 2026-07-04 from
`../../generated-plans-ideas/Loop-Landing-Page-Action-Plan.docx` (a web-agent
draft written with less repo context). The draft's audience framing and
priority ranking survive intact; this refinement grounds every item against
the actual code and adds one finding the draft could not see (a truthfulness
bug in the shipped landing copy — see `01-…`).

## The goal (unchanged from the draft)

The landing page already works for users. Its second audience — recruiters
and founders — currently hits a wall: sign-in is allowlisted, so every claim
on the page is unverifiable to a cold visitor; there is no demo, no
architecture surface, no author link, and the URL reads as scaffolding.

> Target: a recruiter who lands on the URL cold should, within 90 seconds,
> (1) see the product working, (2) find the engineering story, (3) find Shawn.

## What this refinement changed vs. the web draft

1. **Found a live truthfulness bug.** `landing/index.html:585` and `:612`
   claim unverified events are "automatically rolled back." Commit `dba497a`
   fixed exactly this false claim in the SPA (the write manager marks
   `VERIFICATION_FAILED` and does **not** roll back; the plan is simply not
   activated) — but the landing page slipped through that audit. Fixing this
   is now the first increment: the whole point of this pass is that every
   headline claim is checkable, so the page cannot itself contain a false one.
2. **"Rename the Fly app" corrected to a custom-domain attach.** Fly apps
   cannot be renamed in place; renaming means a new app + volume migration
   for a single-machine SQLite deployment. A custom domain via `fly certs`
   on the existing app is cheaper, safer, and fully hides `acme-agentic-cal`.
   The real cost of the migration is the **Google OAuth redirect-URI /
   consent-screen updates**, which the draft did not mention — see `02-…`.
3. **Demo-video beats mapped to real screens** — including the recovery beat
   the draft wanted at 0:45: the 3-option write-failure recovery and the
   replan banner + recovery-mode picker both exist on branch
   `ux-quality-pass` (B1/B2). The video should therefore be recorded **after
   that branch ships and is deployed** — see `04-…` for sequencing and
   staging instructions.
4. **Numbers verified for the "How it's built" page** (as of 2026-07-04,
   branch `ux-quality-pass`): `make check` 2691 green backend, 81 frontend
   tests, 23 axiom docs (`00`–`22`), 8 ADRs, ~$1.70/mo expected LLM spend
   under an $8/mo cap (axiom 09), ~$0.28 onboarding / ~$0.22 replan per
   plan-cycle. All must be **re-verified at ship time**, not copied.
5. **Read-only demo sandbox rescoped.** The keyless dev server
   (`python -m agentic_calendar.app.web`, fixture LLM nodes, fake calendar)
   already is a single-user demo; the remaining work is multi-visitor
   isolation and abuse safety, not product. Stays last, stays optional.

## Increments (one commit each, execution order)

| File | Increment | Effort | Draft's priority |
| --- | --- | --- | --- |
| `01-honest-copy-and-identity.md` | Fix false rollback copy; footer byline + links | ~30 min | Footer: "today" (+ the bug fix, new) |
| `02-domain-migration.md` | Custom domain, OAuth updates, old-URL redirect | ~1 h code + user infra | "this week" |
| `03-how-its-built.md` | Static engineering-story page + nav/footer links | 1–2 days | "this month", very high impact |
| `04-demo-video.md` | Beat sheet, staging, hosting, embed above the fold | ~1 day + recording | "this month", very high impact |
| `05-demo-sandbox.md` | **Deferred.** Multi-visitor keyless demo mode | 2–4 days | "after the above" |

## Sequencing and branch hygiene

- All increments are independent of the backend D/E work in
  `../ux-quality-pass/HANDOFF.md`; none touch `backend/src` engine code.
  Branch from `main` once the open PRs (`deleted-event-memory`,
  `ux-quality-pass`) merge, or stack on `ux-quality-pass` if the user wants
  the video to show B1/B2 recovery (see `04-…`).
- Convention carried over: one commit per increment; the landing stays a
  self-contained static file (inlined tokens, no build step, no external
  assets beyond Google Fonts already present).

## Ground rules

- **Every claim on the page must be true of the deployed version** — not of
  a branch, not of a plan. This is the same honesty rule axiom 08 applies to
  confidence language ("heuristic until calibrated") extended to marketing.
- No analytics, tracking, A/B testing, or CMS (unchanged from
  `../phase-loop-landing.md` non-goals). The privacy posture is part of the
  story; don't undercut it with a tracking embed.
- Landing and new static pages remain outside the React build (L-1 decision
  in `../phase-loop-landing.md` still stands).

## Open questions for the user (blocking only where noted)

1. Portfolio URL and GitHub profile/repo URL for the byline (blocks `01`).
2. Is the repo public, or will it be? (Decides whether `03` links code or
   says "available on request.")
3. Domain choice + purchase (user action; blocks `02` cutover, not the code).
4. The draft mentions two planned engineering blog posts — do they exist yet?
   (`03` links them if so, omits the section if not.)
