# 03 · Service Readiness Beyond Google Verification

Written 2026-07-16. Everything that must be true of the deployed system
before an open beta, independent of the OAuth verification review in
[01](01-google-oauth-verification.md). Ordered roughly by how hard each item
blocks launch.

## 1. Custom domain (blocks verification AND the demo video)

- Status: code side shipped and dormant (`CANONICAL_HOST` redirect in
  `backend/src/agentic_calendar/app/web/server.py`; commented `[env]` slot
  in `fly.toml`). Infra side not done.
- Runbook: `docs/implementation-plans/completed/loop-recruiter-readiness/REMAINING.md`
  §2 — buy domain → `fly certs add` on app `acme-agentic-cal` → add
  Console redirect URI + authorized origin (keep the old fly.dev URI during
  transition) → set `OAUTH_REDIRECT_URI` + `CANONICAL_HOST` → deploy →
  verify OAuth roundtrip on the new host.
- New requirement this folder adds: **verify the domain in Google Search
  Console** with the account that owns the Cloud project — verification
  hard-requires it.
- Cutover side effect: sessions are host-scoped cookies; every existing
  tester re-logs-in.

## 2. Privacy policy page (does not exist — new work)

Nothing in `landing/` or the app mentions a privacy policy today. Required
for verification; also simply owed to beta testers. Content must cover, in
plain language:

- What Google data is accessed: identity (email, name), busy/free ranges,
  and the app-created study calendar. Explicitly: **no event titles,
  descriptions, attendees, or locations from the user's own calendars** —
  the scopes cannot read them and the app never stores raw event text
  (project axiom).
- What is stored and where: account record, plans, telemetry, calendar
  event *mappings* (IDs, not content), in the app's database.
- What is shared: nothing sold or shared with third parties; state the LLM
  provider boundary accurately (plan structure goes to Anthropic; Google
  calendar data does not — re-verify against current prompts before
  publishing the page).
- User controls: disconnect Google (revoke), delete account/data — decide
  and document what deletion actually does before writing the page; if
  there is no self-serve deletion, say "email to request deletion" and
  honor it.
- Retention, contact email, effective date.
- Data-collection language: use [04 §5](04-data-strategy.md) — specific,
  consent-scoped wording ("de-identified skill-progression data …") instead
  of "we collect usage data" boilerplate.

Serve it at `https://<domain>/privacy` as a `landing/` sibling (Dockerfile
already COPYes `landing/`), link it from the landing footer, and paste the
URL into the consent-screen config.

## 3. Anthropic API account posture

- Move the production key to a billed account with an explicit **spend
  limit** and alerting before strangers can trigger generations — beta
  users multiply LLM spend, and the per-run cost figures in the repo
  (~$0.05 smoke, ~$1.70 cumulative dogfood) are single-user numbers.
- Confirm rate limits fit the expected cohort; the repair loop caps retries
  (two per artifact) so worst-case per-user cost is bounded — state the
  bound, don't guess it, by checking token caps in the adapter config.
- Rotate any key that ever appeared in local shell history or logs.

## 4. Data stores

- **App DB:** single SQLite file on one Fly machine (documented posture in
  `docs/deploy.md`). Before beta: put it on a persistent volume (verify
  it already is), add a backup cadence (`fly ssh` + copy-off or Litestream
  — decide), and test a restore once. A beta with real user approvals and
  calendar mappings is the point where "single file, no backups" stops
  being acceptable.
- **Grounding stores: production is EMPTY.** The grounding/RAG layer is
  merged code paths with an unpopulated production store — the curated
  corpus (`corpus.db`, 187-source manifest, snapshot `snap_0217291f46e331b9`)
  lives on the unmerged `grounding-retune-and-ops` worktree branch. Either
  (a) merge that branch and ship the store to prod before beta, or
  (b) consciously launch ungrounded and say so — but don't launch assuming
  grounding is active when the store is empty.
- Concurrency: one process/one machine is fine for a small beta; do not
  scale `fly` machine count >1 while SQLite is the store.

## 5. App-side polish (the original pre-beta list)

Tracked here so this folder is the single launch checklist; details live in
their own plans:

- **Pathway trees** — polish pass; see
  `docs/implementation-plans/narrative-pathways/` (planning docs written
  2026-07-15, not implemented) and
  `docs/implementation-plans/career-track-expansion/` (9 profiles, read
  mechanics + shared-entries docs before adding careers).
- **Database integration** — whatever remains of wiring beyond §4.
- **Unmerged branches audit** — several feature branches are complete but
  unmerged/unpushed (completion-drop-memory stack, ux-quality-pass,
  scheduler-placement-quality worktree, grounding worktree). Decide what is
  *in* the beta build, merge that set, and deploy it — the beta should not
  run from a branch soup.

## 6. Post-publication doc updates

- `docs/deploy.md`: §1 scope list is stale (says `calendar.events`; the web
  flow requests `calendar.app.created` + `calendar.freebusy`) and its
  "choose In production (unverified)" guidance becomes wrong the moment
  verification is submitted. Update after the Google side settles.
- Landing page: once verified, the consent flow is clean — remove any
  tester-facing instructions about clicking through the unverified warning
  if any were written.
