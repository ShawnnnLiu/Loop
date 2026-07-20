# Publication Requirements — Loop Beta

Written 2026-07-16. Researched against Google's OAuth verification docs as of
that date (sources linked in each doc). Numbers quoted from Google (review
timelines, user caps) are their published figures, not measurements.

## Why this folder exists

Opening the beta to testers **without manually adding each one** in Google
Cloud Console means moving the OAuth consent screen from **Testing** to
**In production**. Because Loop requests at least one *sensitive* Google
scope (`calendar.freebusy`), full production status without warnings or user
caps requires **Google's sensitive-scope OAuth verification** — a review
process with its own prerequisites (owned domain, privacy policy, demo
video). That process, not app polish, is the long pole for an open beta.

The good news: Calendar scopes are *sensitive*, not *restricted* — the
expensive CASA security assessment (Gmail/Drive tier) does **not** apply.

## The decision

Two viable paths; they are not mutually exclusive (start B, run A in
parallel):

| Path | Tester experience | Cap | Lead time |
| --- | --- | --- | --- |
| **A. Verified production** ([01](01-google-oauth-verification.md)) | Clean consent screen, no warnings | None | Domain + privacy policy + video, then ~10 days Google review (often weeks with back-and-forth) |
| **B. Unverified production** ([02](02-interim-unverified-beta.md)) | "Google hasn't verified this app" warning, click-through | **100 users, lifetime of the project, never resets** | Immediate |

Staying in **Testing** status is the worst of both: manual tester list (max
100) *and* refresh tokens that expire every 7 days (weekly reconnect).

## Docs in this folder

- [01-google-oauth-verification.md](01-google-oauth-verification.md) —
  scope inventory + classification, everything Google requires for
  verification, draft per-scope justifications, demo-video requirements.
- [02-interim-unverified-beta.md](02-interim-unverified-beta.md) — the
  publish-unverified interim path and its tradeoffs; current Testing-status
  behavior.
- [03-service-readiness.md](03-service-readiness.md) — everything else that
  must be true before beta: domain cutover, privacy policy (does not exist
  yet), Anthropic billing, production grounding stores (empty), persistence,
  and the app-side polish list.
- [04-data-strategy.md](04-data-strategy.md) — long-term data collection
  without PII: pathway × mastery learning curves as the durable asset,
  built on the existing TelemetryEvent / pooled-model / axiom-07 consent
  pattern; feeds the privacy-policy language in 03 §2.

## Execution order (checklist)

Tags: **[user]** = only you can do it; **[agent]** = hand to a session once
its inputs exist.

1. [ ] **[user]** Decide path A / B / B-then-A (recommendation in
   [02](02-interim-unverified-beta.md): B-then-A if beta starts before
   verification lands and the early cohort is small).
2. [ ] **[user]** Buy the custom domain and run the cutover — the existing
   runbook is `docs/implementation-plans/completed/loop-recruiter-readiness/REMAINING.md`
   §2 (fly certs → Console redirect URI → `CANONICAL_HOST`). A `*.fly.dev`
   host **cannot** pass Google's domain-ownership check, so this is
   load-bearing for verification, not just branding.
3. [ ] **[user]** Verify the domain in Google Search Console (same Google
   account that owns the Cloud project).
4. [ ] **[agent]** Write and serve a privacy policy page on that domain;
   link it from the landing page (see
   [03 §2](03-service-readiness.md); data-collection language comes from
   [04 §5](04-data-strategy.md)). None exists today.
5. [ ] **[user]** Publish the consent screen to production (Console →
   "Publish App"). This alone fixes the 7-day token expiry.
6. [ ] **[user]** Submit verification in the Console **Verification
   Center**: confirm scope classifications, paste the per-scope
   justifications drafted in [01 §4](01-google-oauth-verification.md),
   attach the demo video.
7. [ ] **[user]** Record the verification demo video ([01 §5](01-google-oauth-verification.md)) —
   distinct from the recruiter-readiness marketing video; it must show the
   consent screen and scope usage with the URL bar visible.
8. [ ] **[user]** Respond to Google review feedback until approved.
9. [x] **[agent]** Done 2026-07-19: `docs/deploy.md` §1 now documents the
   real web scopes (`calendar.app.created` + `calendar.freebusy`), HTTPS-only
   redirect URIs (plain-http URIs block adding granular scopes in Data
   Access), the unverified 100-user lifetime cap, and the rule that the web
   client stays the project's only OAuth client (the operator CLI's Desktop
   client was deleted from the production project the same day).
10. [ ] Service readiness items in [03](03-service-readiness.md) (Anthropic
    billing/limits, grounding stores, backups, pathway-tree polish) — can
    proceed in parallel with 1–8.
