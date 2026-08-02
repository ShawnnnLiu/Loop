# Publication Requirements — Loop Beta

Written 2026-07-16. Researched against Google's OAuth verification docs as of
that date (sources linked in each doc). Numbers quoted from Google (review
timelines, user caps) are their published figures, not measurements.

## Status 2026-07-31: RESOLVED - verification not required

Branding verification passed (manual review, after the automated bounces logged in [01](01-google-oauth-verification.md)).
The console Data Access page now classifies **every** requested scope - including `calendar.app.created` and freebusy - as **non-sensitive**, and states: "Verification is not required since your app is not requesting any sensitive or restricted scopes."
The premise this folder was written under (freebusy puts the app in the sensitive-scope tier) no longer holds for this app.

Consequences:

- No sensitive-scope verification review.
- No demo video ([01 §5](01-google-oauth-verification.md)).
- No 100-user lifetime cap and no "unverified app" warning ([02](02-interim-unverified-beta.md)) - both only ever applied to unapproved sensitive scopes.
- The path A / path B decision below is dissolved; there is only one path and it has no review step.

The one remaining Google-side action is publishing the consent screen to production (checklist item 5), which is instant with non-sensitive scopes and ends the 7-day refresh-token expiry plus the manual tester list.
Beta access stays gated app-side by `TESTER_ALLOWLIST`.
The non-Google readiness items in [03](03-service-readiness.md) still apply.
The rest of this folder is kept as written, as a record of the process; per-doc status notes mark what is now moot.

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

1. [x] Moot 2026-07-31 - no verification tier applies, so the A/B
   decision dissolved (see Status at top).
2. [x] **[user]** Done 2026-07-19 - loop-study.com bought and cut over
   (fly certs, Console redirect URI, `CANONICAL_HOST`; runbook was
   `docs/implementation-plans/completed/loop-recruiter-readiness/REMAINING.md` §2).
3. [x] **[user]** Done 2026-07-19 - domain verified in Google Search
   Console (TXT record, dig-confirmed).
4. [x] **[agent]** Done 2026-07-19 - `/privacy` + `/terms` live on
   loop-study.com, linked from the landing footer (PRs #36, #37, #38).
5. [ ] **[user]** Publish the consent screen to production (Console →
   "Publish App"). This alone fixes the 7-day token expiry. With
   non-sensitive scopes only, this is instant and needs no review.
6. [x] Partially done 2026-07-19 (per-scope justifications submitted in
   the Verification Center), then moot 2026-07-31 - no scope review
   exists for this app.
7. [x] Moot 2026-07-31 - demo video not required (it existed only for
   sensitive-scope review).
8. [x] Done 2026-07-31 - branding review passed; no scope review follows.
9. [x] **[agent]** Done 2026-07-19: `docs/deploy.md` §1 now documents the
   real web scopes (`calendar.app.created` + `calendar.freebusy`), HTTPS-only
   redirect URIs (plain-http URIs block adding granular scopes in Data
   Access), the unverified 100-user lifetime cap, and the rule that the web
   client stays the project's only OAuth client (the operator CLI's Desktop
   client was deleted from the production project the same day).
10. [ ] Service readiness items in [03](03-service-readiness.md) (Anthropic
    billing/limits, grounding stores, backups, pathway-tree polish) — can
    proceed in parallel with 1–8.
