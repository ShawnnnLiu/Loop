# Remaining Work — Recruiter Readiness

Written 2026-07-05, after the agent-side pass shipped on branch
`loop-recruiter-readiness` (4 commits: `39f37b1` honest copy + byline,
`c827771` canonical-host redirect, `52cebbc` how-its-built page, `d325de8`
staging checklist + plan docs). Branch is **pushed**; PR to open at
<https://github.com/ShawnnnLiu/Agentic-Calendar/compare/main...loop-recruiter-readiness>
(summary text was handed over in-session).

Everything below is what the branch does **not** finish, in execution order.
Tags: **[user]** = only you can do it; **[agent]** = hand to a session once its
inputs exist.

## 0 · Land the branch

- [ ] **[user]** Open the PR from the compare URL and merge it.
- [ ] **[user]** Before pulling merged `main` into this checkout: this plan
      folder is currently **untracked** here, and the same 7 files are
      committed on the branch. `git pull` will refuse to overwrite them —
      delete the local untracked copies first (this `REMAINING.md` is new and
      safe to keep). The worktree at `.claude/worktrees/loop-recruiter-readiness`
      can be removed after merge: `git worktree remove .claude/worktrees/loop-recruiter-readiness`.
- [ ] **[user]** Deploy (`fly deploy`) so increments 01 + 03 are actually
      live — the honesty rule is "true of the deployed version," and until
      this deploy the live landing still carries the false rollback claim.

## 1 · Increment 01 leftovers (identity)

- [ ] **[user]** Provide the portfolio URL.
- [ ] **[agent]** Add it to the byline on both pages ("Built by Shawn Liu"
      then links portfolio; GitHub link stays).
- [ ] **[user]** Decide: is the repo public (or will it be)?
- [ ] **[agent]** If public: swap "code walkthrough available on request" on
      `/how-its-built` for a direct repo link (and optionally link the repo,
      not just the profile, in the footers).

## 2 · Increment 02 — domain cutover (mostly user infra)

The code side is deployed-but-dormant: the redirect only activates when
`CANONICAL_HOST` is set. Order matters; OAuth breaks hard if 2.3 and 2.4
don't both happen before the deploy that flips the redirect URI.

- [ ] **[user]** 2.1 Buy the domain (~$10; availability decides).
- [ ] **[user]** 2.2 `fly certs add <domain>` on app `acme-agentic-cal`, add
      the DNS records `fly certs show <domain>` asks for, wait for issuance.
- [ ] **[user]** 2.3 Google Cloud Console: **add** redirect URI
      `https://<domain>/auth/callback` + the new authorized JavaScript
      origin + the domain on the consent screen. **Keep the old fly.dev URI
      registered during transition.**
- [ ] **[user or agent]** 2.4 fly.toml `[env]`: set
      `OAUTH_REDIRECT_URI = "https://<domain>/auth/callback"` and
      `CANONICAL_HOST = "<domain>"` (the commented block in fly.toml marks
      the spot), commit, deploy.
- [ ] **[user]** 2.5 Verify: full OAuth roundtrip on the new domain
      (login → consent → callback → /app), old fly.dev URL 301s
      path-preserving, `/healthz` 200 on both hosts.
- [ ] **[user]** Heads-up to testers: sessions are host-scoped cookies —
      everyone re-logs-in after cutover.
- [ ] **[user]** Later, optional: remove the old redirect URI from the OAuth
      client once traffic is clean.

## 3 · Increment 03 leftovers (how-its-built)

- [ ] **[agent]** Only if the merge/deploy slips well past 2026-07-05 or big
      branches (e.g. `calendar-authoritative-moves`) merge first: re-measure
      the numbers on the page (2,748 backend / 88 frontend / 23 axioms /
      8 ADRs / ~$1.70 under $8) — they must be true of the deployed commit.
- [ ] **[user, 2 min]** Residual from the pass: a real-browser spot-check of
      `/how-its-built` at a phone width (the diagram should scroll inside its
      own container; the page body should never scroll horizontally).

## 4 · Increment 04 — demo video

Preconditions (all before recording): PR merged **and deployed**, domain
cutover done (the outro shows the URL). Then:

- [ ] **[user]** Record the ~90s video per `04-demo-video.md` beats +
      `04a-demo-staging-checklist.md` staging recipe (replan beat: motivation
      profile set to ask-each-time, one missed check-in, Week screen →
      chip → banner → recovery-mode picker). Dedicated tester Google account,
      no real personal data on screen.
- [ ] **[agent]** Once footage exists: compress to H.264 MP4 ≤ 15–20 MB,
      poster frame, WebVTT captions, `<video controls preload="metadata">`
      embed above the fold on the landing, responsive check at ≤ 820px,
      served as a `landing/` sibling asset (Dockerfile already COPYes
      `landing/`). Self-hosted — no YouTube iframe.

## 5 · Increment 05 — demo sandbox (still deferred)

Do not start until: 01–04 shipped, the video has been live long enough to
judge insufficient (e.g. recruiters asking to "try it"), and you explicitly
green-light the 2–4 day effort. Scope refinement lives in `05-demo-sandbox.md`.
