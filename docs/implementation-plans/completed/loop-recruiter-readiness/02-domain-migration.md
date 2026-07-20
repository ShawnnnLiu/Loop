# 02 · Domain Migration — Drop "acme-agentic-cal"

The URL will sit on a resume; `acme-agentic-cal.fly.dev` reads as template
scaffolding. The web draft said "buy a domain or at minimum rename the Fly
app" — **refinement: do not rename the app.** Fly apps can't be renamed in
place; a rename means a new app plus migrating the `data` volume backing the
single-machine SQLite store. Attach a custom domain to the existing app
instead: same effect on every user-visible surface, no data migration.

## Current state (verified)

- `fly.toml` (repo root): `app = "acme-agentic-cal"`, and — the part the
  draft missed — `OAUTH_REDIRECT_URI = "https://acme-agentic-cal.fly.dev/auth/callback"`
  is baked into `[env]`. The domain is load-bearing for Google OAuth, not
  just cosmetic.
- Secrets (`GOOGLE_OAUTH_CLIENT_SECRET_JSON`, allowlist, session keys) are
  Fly secrets — **untouchable by the agent** per the operating contract. All
  OAuth-console and DNS steps below are user actions.

## Steps

1. **User: buy the domain** (~$10; any clean variant — the draft suggests
   `looploop.dev`, `useloop.app`, `getloop.sh`; availability decides).
2. **User: point DNS at Fly** and provision the cert:
   `fly certs add <domain>` on app `acme-agentic-cal`, then the A/AAAA or
   CNAME records `fly certs show` asks for. Wait for issuance.
3. **User: update the Google OAuth client** (Cloud Console): **add** the new
   redirect URI `https://<domain>/auth/callback` and the new authorized
   JavaScript origin; add the domain to the consent screen's authorized
   domains. **Keep the old fly.dev URI during transition** so a half-migrated
   deploy can't lock everyone out.
4. **Code: config + redirect** (the only agent-side changes, one commit):
   - `fly.toml` `[env]`: `OAUTH_REDIRECT_URI` → the new domain.
   - Old-URL forwarding: a tiny host-check in the FastAPI app
     (`backend/src/agentic_calendar/app/web/app.py` — register before the
     landing route at `app.py:160-164`): requests whose `Host` is
     `acme-agentic-cal.fly.dev` get a 301 to the same path on the new domain,
     driven by an optional env var (e.g. `CANONICAL_HOST`) so dev/test
     environments are unaffected. Nothing breaks for anyone holding the old
     URL; the resume links the new one.
   - Grep for other hardcoded `acme-agentic-cal` occurrences (README, docs)
     and update.
5. **User: deploy + verify**: full OAuth roundtrip on the new domain
   (login → consent → callback → app), old URL redirects, `/healthz` fine.
6. **Later (optional):** remove the old redirect URI from the OAuth client
   once traffic is confirmed clean.

## Gotchas the draft didn't have

- **Sessions are host-scoped cookies** — every tester re-logs-in after
  cutover. Acceptable at ≤100 testers; worth a heads-up message.
- OAuth breaks **hard** if step 3 and step 4 don't both happen before the
  deploy that flips `OAUTH_REDIRECT_URI` — hence keeping both URIs
  registered during transition.
- `APP_HTTPS_ONLY=1` stays; Fly terminates TLS for custom domains the same
  way.

## Ask-user gates

Domain purchase, DNS, Fly cert commands, and OAuth-console edits are all
networked and/or credential-adjacent: **user performs them** (or explicitly
green-lights each command). The agent's scope is step 4 only.

## Acceptance criteria

- The product, OAuth flow, and landing all work on the new domain.
- The old fly.dev URL 301s to the new domain (path-preserving).
- No occurrence of `acme-agentic-cal` remains in user-visible surfaces.
