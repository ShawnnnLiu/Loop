# 02 · Interim Path: Unverified Production, and Today's Testing Status

Written 2026-07-16.

## Where the app is today: Testing status

The consent screen is in **Testing** status. Consequences:

- Every tester must be **manually added** to the test-user list in the
  Console (hard max 100 test users).
- **Refresh tokens expire after 7 days** because the app requests scopes
  beyond `email`/`profile`/`openid` — every tester reconnects Google
  weekly. This is a Testing-status behavior, not a bug in the token store.

Both go away on publishing to production; only the warning screen and user
cap depend on *verification*.

## The unverified-production option

Console → "Publish App" without submitting for verification:

- Testers no longer need to be pre-added; anyone with the URL can connect.
- Refresh tokens stop expiring weekly.
- Every tester sees the **"Google hasn't verified this app"** interstitial
  before consent. It is click-through-able ("Advanced" → "Go to <app>
  (unsafe)") but reads alarming to non-technical users.
- **Lifetime cap: 100 users** may grant the unapproved sensitive scopes,
  counted over the *lifetime of the Cloud project*. The cap **never resets
  and cannot be raised** — users who later revoke access still count, and
  burning the cap before verification lands means new users are blocked
  until it does.

`docs/deploy.md` §1 step 4 already documents this posture for the closed
dogfood group — that framing stays correct **only** while the total
ever-connected user count stays comfortably under 100.

## Recommendation (heuristic)

**B-then-A:** publish unverified now if the early beta cohort is small and
known (double-digit), and submit verification in parallel
([01](01-google-oauth-verification.md)). Rationale:

- The 7-day reconnect is the most acutely painful current behavior and
  publishing fixes it immediately, before the domain/privacy-policy work
  finishes.
- The lifetime cap is the real risk. Mitigate by not sharing the URL
  publicly (no launch posts, no `/how-its-built` traffic converting to
  sign-ups) until verification is approved.
- If the plan is to open the beta wide from day one, skip this path — go
  straight to verified production and gate the start date on Google's
  review.

## Sources

- [Unverified apps & the 100-user cap](https://support.google.com/cloud/answer/7454865)
- [OAuth app state overview](https://developers.google.com/identity/protocols/oauth2/production-readiness/overview)
- [Manage app audience](https://support.google.com/cloud/answer/15549945)
