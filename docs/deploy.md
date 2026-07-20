# Hosted deploy runbook (closed multi-user dogfood)

The hosted web app lets a closed group of **≤100 known testers** sign in with
Google, connect their calendar, and run the propose → approve → write cycle
through a basic UI. At this scale the app can run **unverified** (warning
screen + a 100-user lifetime cap — see step 4). The Calendar scopes below are
*sensitive*, not *restricted*, so even full verification involves no
security-assessment step; the verification path is documented in
`docs/publication-requirements/`.

This is a single-instance MVP: one process, one SQLite file. It is the explicit
superset of the documented single-user Stage 0 (`phase-frontend-mvp.md`); the
deterministic core and every axiom-06 invariant are unchanged.

## 1. Google Cloud Console (one-time)

1. Create an **OAuth client of type "Web application"**, and keep it the
   **only** OAuth client in the project. Google's Verification Center flags
   every scope the project's clients *actually request*, so a stray Desktop
   client (e.g. for the operator CLI) drags its scopes into the verification
   surface — the operator CLI belongs in a separate personal project.
2. **Authorized redirect URI** = `https://<your-domain>/auth/callback`.
   HTTPS only — do **not** add `http://localhost...` URIs: any plain-http
   URI or JavaScript origin on a client blocks adding the granular Calendar
   scopes on the Data Access page ("restricted to projects using HTTPS URLs
   only"). Local development uses the keyless dev server
   (`python -m agentic_calendar.app.web`), which never touches Google OAuth.
3. On the **Data Access** page, add scopes: `openid`, `email`, `profile`,
   `https://www.googleapis.com/auth/calendar.app.created`, and
   `https://www.googleapis.com/auth/calendar.freebusy` — exactly the
   `WEB_SCOPES` in `tools/google_oauth_web.py`. Never add `calendar.events`;
   the web flow does not request it.
4. Choose **"In production" (unverified)** so refresh tokens do not expire every
   7 days. Users see a one-time "Google hasn't verified this app" warning they
   click through, and unverified apps carry a **100-user lifetime cap that
   never resets** (`docs/publication-requirements/02-interim-unverified-beta.md`).
   (Alternatively keep **Testing** + add each tester as a test user, accepting
   weekly re-auth.) Dropping the warning and the cap requires sensitive-scope
   verification (`docs/publication-requirements/01-google-oauth-verification.md`).
5. Download the web client JSON. Keep it out of the repo (`client_secret*.json`
   is gitignored); place it on the host as a secret file.

## 2. Configuration (environment variables)

| Variable | Purpose |
|---|---|
| `SHARED_DB_PATH` | SQLite file path on a **persistent volume** (all per-user data). |
| `GOOGLE_OAUTH_CLIENT_SECRET_JSON` *or* `GOOGLE_OAUTH_CLIENT_SECRET_FILE` | The Web client JSON from step 1 — inline (env-var hosts like Fly) or a file path. |
| `OAUTH_REDIRECT_URI` | Must equal the Authorized redirect URI exactly. |
| `APP_SESSION_SECRET` | Random secret for signing the session cookie. |
| `APP_TOKEN_ENCRYPTION_KEY` | Fernet key for encrypting OAuth tokens at rest. |
| `TESTER_ALLOWLIST` | Comma-separated emails permitted to sign in (the in-app ≤100 gate). |
| `ANTHROPIC_API_KEY` | Required — real plans use the live Anthropic nodes. |
| `APP_HTTPS_ONLY` | `1` (default) in production; `0` only for local http runs. |
| `TUNING_PATH` | Optional `tuning.toml` (overrides journaled to the change log). |

Generate the two keys once and store them as secrets:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"  # APP_TOKEN_ENCRYPTION_KEY
python -c "import secrets; print(secrets.token_urlsafe(48))"                                # APP_SESSION_SECRET
```

> Rotating `APP_TOKEN_ENCRYPTION_KEY` makes already-stored tokens
> undecryptable — affected users simply re-connect Google. Rotating
> `APP_SESSION_SECRET` logs everyone out.

## 3. Run

Single process only — SQLite + WAL is a one-process store, so **do not add
`--workers`**.

```bash
uv run uvicorn agentic_calendar.app.web.server:create_hosted_app \
    --factory --host 0.0.0.0 --port 8000
```

Or via the image. It is **multi-stage**: it builds the React SPA
(`frontend/dist`) and bundles it plus the static landing page, so the one
container serves the whole product — the landing at `/`, the SPA app routes, and
the JSON API. The build context is the **repo root** (it needs `frontend/` and
`landing/`, siblings of `backend/`), so build from the repo root and point at
`backend/Dockerfile`:

```bash
docker build -t agentic-calendar -f backend/Dockerfile .   # from the repo root
docker run -p 8000:8000 \
    -v /srv/agentic-calendar:/data \
    -e SHARED_DB_PATH=/data/app.db \
    -e GOOGLE_OAUTH_CLIENT_SECRET_FILE=/run/secrets/client.json \
    -e OAUTH_REDIRECT_URI=https://<your-domain>/auth/callback \
    -e APP_SESSION_SECRET=... -e APP_TOKEN_ENCRYPTION_KEY=... \
    -e TESTER_ALLOWLIST="a@example.com,b@example.com" \
    -e ANTHROPIC_API_KEY=... \
    -v /run/secrets/client.json:/run/secrets/client.json:ro \
    agentic-calendar
```

Terminate TLS in front of the app (the platform's load balancer, or Caddy for
automatic HTTPS) so the public URL is `https://<your-domain>`.

### Fly.io (single machine + volume)

`fly.toml` lives at the **repo root** (preconfigured); edit `app`,
`primary_region`, and `OAUTH_REDIRECT_URI` to match your app name. Run flyctl
from the repo root — `fly.toml` is auto-detected, which sets the build context to
the root (the image builds the SPA, so it needs `frontend/` and `landing/`,
siblings of `backend/`):

```bash
# from the repo root — fly.toml is picked up automatically
fly launch --no-deploy --copy-config --name <your-app>
fly volumes create data --region <region> --size 1   # persistent SQLite
fly secrets set \
  APP_SESSION_SECRET="$(python -c 'import secrets;print(secrets.token_urlsafe(48))')" \
  APP_TOKEN_ENCRYPTION_KEY="$(python -c 'from cryptography.fernet import Fernet;print(Fernet.generate_key().decode())')" \
  TESTER_ALLOWLIST="a@example.com,b@example.com" \
  ANTHROPIC_API_KEY="sk-ant-..." \
  GOOGLE_OAUTH_CLIENT_SECRET_JSON="$(cat client_secret.json)"
fly deploy   # build context is the repo root, where fly.toml lives
fly scale count 1   # exactly one machine — SQLite is single-process
```

The public URL is `https://<your-app>.fly.dev`; its `/auth/callback` must be
the Authorized redirect URI from step 1. Watch the first `fly deploy` build log:
the Node stage runs `npm ci && npm run build`, then the Python stage copies
`frontend/dist` + `landing/` into the image.

## 4. Operate

- **Back up the volume** holding `SHARED_DB_PATH` — it contains personal data
  and encrypted refresh tokens.
- Add/remove testers by editing `TESTER_ALLOWLIST` and restarting.
- A signed-in tester completes the whole loop in the **React SPA**: the landing
  at `/` → Connect Google → onboarding wizard → generate → drag-adjust → approve
  → write/verify → today/check-in. (The JSON API at `/api/*` still backs every
  step and remains directly callable.)

## 5. Smoke-test after deploy

Run this after **every** deploy, against the live canonical host — not
localhost, and not just `/healthz`. Local tests passing says nothing about
route registration in the image, Dockerfile ENV overrides, HEAD handling, or
cache behavior; each of those has silently diverged from green local checks
before (the `/privacy` SPA fallthrough, the HEAD 405 that bounced Google's
branding checker).

```bash
HOST=https://loop-study.com   # the canonical host (CANONICAL_HOST)

# Health + API gate
curl -s $HOST/healthz                                      # {"status":"ok"}
curl -s -o /dev/null -w '%{http_code}\n' $HOST/api/status  # 401 (session-gated)

# Every HTML page: GET must return the REAL page. Assert content, not status —
# a 200 can be the SPA shell squatting on the URL after a fallthrough.
curl -s $HOST/              | grep -c '<title>Loop — interview prep'    # 1
curl -s $HOST/privacy       | grep -c '<title>Loop — privacy policy'    # 1
curl -s $HOST/terms         | grep -c '<title>Loop — terms of service'  # 1
curl -s $HOST/how-its-built | grep -c '<title>Loop — how it'            # 1
curl -s $HOST/app           | grep -c 'id="root"'                       # 1 (SPA shell)

# Every HTML page: HEAD must be 200. Automated checkers (Google's branding
# crawler among them) probe with HEAD; a 405 here reads as a broken site.
for p in / /privacy /terms /how-its-built /app; do
  curl -sI -o /dev/null -w "HEAD $p -> %{http_code}\n" $HOST$p          # all 200
done

# HTML responses must force revalidation, or a stale SPA shell stays cached
# per-URL in visitors' browsers indefinitely.
curl -sI $HOST/ | grep -ic 'cache-control: no-cache'                    # 1

# Canonical-host redirects (http and www variants both 301 to the apex)
curl -s -o /dev/null -w '%{http_code} -> %{redirect_url}\n' http://loop-study.com/
curl -s -o /dev/null -w '%{http_code} -> %{redirect_url}\n' https://www.loop-study.com/
```

Maintenance rule: any change that adds, moves, or re-serves an HTML route must
add its GET-content and HEAD lines here in the same change (see AGENTS.md,
Deploy Verification Rules).

External reviewers (Google OAuth / branding verification): do not resubmit
until this checklist passes against the live host, and treat a rejection as
real only when its findings email exists — the console panel keeps showing the
previous attempt's findings until a new decision lands.

Then open `https://loop-study.com/` in a browser, click **Connect Google
Calendar**, sign in with an allowlisted account, and walk the wizard → approve →
write. A non-allowlisted account is rejected at `/auth/callback` with 403 — add
it to `TESTER_ALLOWLIST` and restart.
