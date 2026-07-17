# 01 · Google OAuth Sensitive-Scope Verification

Written 2026-07-16 against Google's published process. Google changes this
process periodically — re-check the linked docs before submitting.

## 1. Scope inventory (what the app actually requests)

Source of truth: `WEB_SCOPES` in
`backend/src/agentic_calendar/tools/google_oauth_web.py:32`.

| Scope | Purpose in Loop | Classification |
| --- | --- | --- |
| `openid` | Sign-in | Non-sensitive |
| `userinfo.email` | Account identity | Non-sensitive |
| `userinfo.profile` | Display name | Non-sensitive |
| `calendar.app.created` | Create the app's secondary calendar and manage events **on that calendar only** | Confirm in Verification Center (granular scope introduced 2024; treat as sensitive until the Console says otherwise) |
| `calendar.freebusy` | Read busy/free ranges only — never event content — so the scheduler avoids existing commitments | **Sensitive** |

One sensitive scope is enough to put the whole app in the sensitive-scope
verification tier. All Calendar scopes are *sensitive*, not *restricted*:
**no CASA/security assessment is required** (that tier is Gmail, Drive,
Fitness, etc.).

The Console **Verification Center** (APIs & Services → OAuth consent screen)
shows the authoritative per-scope classification when you prepare the
submission — trust it over this table.

Note: the operator CLI (`google_calendar_auth.py`) uses `calendar.events`,
but that is a separate Desktop client used only by you; verification concerns
the web client's consent screen. Do **not** add `calendar.events` to the web
consent screen — the narrow scopes are both a better review story and less
to justify.

## 2. What verification requires — the full list

1. **Publishing status: In production.** Console → OAuth consent screen →
   "Publish App". (Publishing *without* verification is path B — see
   [02](02-interim-unverified-beta.md).)
2. **An owned domain, verified in Google Search Console** by the same
   account that owns the Cloud project. `*.fly.dev` cannot pass this —
   you can't prove ownership of a shared apex. The custom-domain cutover
   runbook already exists:
   `docs/implementation-plans/loop-recruiter-readiness/REMAINING.md` §2.
   Every domain Google sees — homepage, privacy policy URL, authorized
   redirect URIs — must belong to you and be listed as an authorized domain.
3. **App homepage** on that domain that genuinely describes what the app
   does. A bare login page gets rejected. `landing/index.html` qualifies
   once it is served from the verified domain.
4. **Privacy policy URL** on the same verified domain, linked from the
   homepage, describing how Google user data is collected, used, stored,
   and shared — consistent with the
   [Google API Services User Data Policy](https://developers.google.com/terms/api-services-user-data-policy).
   **Does not exist today** — see [03 §2](03-service-readiness.md).
5. **Per-scope written justification** (§4 below has drafts).
6. **Demo video** (§5 below).
7. **Accurate consent-screen branding.** App name must match the homepage;
   support email and developer contact must be current. Uploading a **logo**
   triggers an additional brand-verification step — consider submitting
   without a logo first to reduce review surface (heuristic, not a rule).

## 3. Timeline and review mechanics

- Google quotes **up to ~10 days** for sensitive-scope review once a
  *complete* submission is in. Incomplete submissions bounce; real-world
  end-to-end is commonly a few weeks of back-and-forth. Start before the
  beta date, not on it.
- Review happens in the Console **Verification Center**; feedback arrives
  by email to the developer contact.
- **Re-verification is triggered by adding new sensitive/restricted scopes
  later.** Relevant to roadmap items that might widen calendar access —
  keep new features inside `calendar.app.created` + `calendar.freebusy` if
  at all possible.

## 4. Draft per-scope justifications

The architecture is the story: deterministic engine, app-created calendar
only, busy/free only, approval-gated writes. Adapt, don't pad — reviewers
want the narrow factual claim.

**`calendar.app.created`:**
> Loop creates one dedicated secondary calendar ("study plan" calendar) in
> the user's account and writes approved study-session events to it. All
> event creation, update, and rollback happens exclusively on this
> app-created calendar. Every write requires an explicit in-app user
> approval step. The app cannot see or modify events on any other calendar
> with this scope, which is why it was chosen over broader alternatives.

**`calendar.freebusy`:**
> Loop's scheduler places study sessions into free time. It queries
> busy/free ranges only, to avoid double-booking the user's existing
> commitments. Event titles, descriptions, attendees, and locations are
> never accessible with this scope and are never requested. Busy ranges are
> used transiently for schedule computation.

**`openid` / `userinfo.email` / `userinfo.profile`:** sign-in and account
identity; no justification text needed (non-sensitive), but they must be
declared on the consent screen.

## 5. Demo video requirements

This is **not** the recruiter-readiness marketing video
(`loop-recruiter-readiness/04-demo-video.md`) — different audience,
different rules. Requirements:

- Hosted on YouTube; **unlisted is fine**. (The recruiter video plan is
  self-hosted MP4 — that won't work here; Google asks for a YouTube link.)
- In English, or with English captions.
- Shows the **full OAuth flow from the app**: click sign-in → Google
  consent screen displaying the app name and the requested scopes → grant.
- **Browser URL bar visible** throughout, showing the app running on the
  verified domain (this is why the domain cutover must land first).
- Demonstrates **how the app uses each sensitive scope**: show the
  app-created calendar receiving an approved event
  (`calendar.app.created`), and show the scheduler working around existing
  busy time (`calendar.freebusy` — e.g. Week view avoiding a busy block).
- Use a dedicated tester Google account; no real personal data on screen
  (the staging recipe in
  `loop-recruiter-readiness/04a-demo-staging-checklist.md` is reusable for
  setup, even though the beats differ).

## 6. Compliance posture to state in the submission

Facts that are already true and worth saying explicitly:

- No raw calendar event titles/descriptions are stored (project axiom;
  enforced in the write path).
- Calendar writes are draft-first, approval-gated (`approval_event_id`),
  hash-rechecked, verified after write, and reversible via stored event
  mappings.
- Busy/free data is read-only input to a deterministic scheduler; it is not
  shared with third parties and is not used for advertising or model
  training. (Google user data is **not** sent to the LLM provider —
  planner prompts contain plan structure, not calendar reads. Verify this
  statement against the current prompt-exposure table before submitting:
  `docs/implementation-plans/resume-intake-onboarding/` documents the
  pattern.)

## Sources

- [Sensitive scope verification](https://developers.google.com/identity/protocols/oauth2/production-readiness/sensitive-scope-verification)
- [OAuth app state overview](https://developers.google.com/identity/protocols/oauth2/production-readiness/overview)
- [Submitting your app for verification](https://support.google.com/cloud/answer/13461325)
- [OAuth App Verification Help Center](https://support.google.com/cloud/answer/13463073)
- [When verification is not needed](https://support.google.com/cloud/answer/13464323)
- [Calendar API scopes](https://developers.google.com/workspace/calendar/api/auth)
