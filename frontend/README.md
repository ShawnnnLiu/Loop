# Loop frontend

The hi-fi **Loop** product UI — a React + Vite + TypeScript SPA that is a thin
client of the FastAPI JSON API (`/api/*`) and the server-side Google OAuth flow
(`/auth/*`). No control-plane logic lives here: routing, validation, scheduling,
the approval gate, the payload-hash recheck, calendar writes, and verification
all stay server-side. The SPA renders state and sends intents.

See `docs/implementation-plans/phase-loop-mvp-frontend.md` for the full plan and
the commit breakdown (F-A…F-H).

## Develop

Two ways to run the SPA against a real backend.

**A · Vite dev server with hot-reload (active development).** The Vite dev
server proxies `/api`, `/auth`, and `/healthz` to the keyless backend, so run
that on `:8000` first (fixture LLM nodes, no Anthropic key, no Google — the
sample profile is auto-onboarded so `propose` works out of the box):

```bash
# terminal 1 — keyless dev backend (from backend/), serves the fixture env on :8000
cd ../backend && uv run python -m agentic_calendar.app.web

# terminal 2 — frontend with hot-reload
npm install
npm run dev          # http://localhost:5173  (proxies /api,/auth,/healthz → :8000)
```

**B · Production-like single server (verify the cutover).** Build the SPA, then
the same keyless backend serves the static landing at `/` and the SPA at the app
routes (entry `/app`):

```bash
npm run build                                        # writes frontend/dist/
cd ../backend && uv run python -m agentic_calendar.app.web   # http://127.0.0.1:8000
```

`/` is the landing (`landing/index.html`); `/app`, `/today`, … serve the SPA
(`index.html` fallback) so the client router boots. In production
(`server:create_hosted_app`) the backend serves these the same way — `/api`,
`/auth`, `/healthz` win over the SPA catch-all; `SPA_DIST_DIR` / `LANDING_INDEX`
override the locations. There is no Vite in production. This is the F-H cutover
(the Jinja page surface was retired) plus the L-B landing.

## Checks (the per-commit frontend gate)

```bash
npm run typecheck    # tsc --noEmit
npm run lint         # eslint
npm run test         # vitest run — unit tests for the pure logic
npm run build        # tsc --noEmit && vite build
```

Unit tests cover the pure, high-risk logic: the tz/week math in
`src/lib/datetime.ts` and the API client's request handling in `src/api/client.ts`
(200 / 401-redirect / 4xx-ApiError / workflow-failure-as-result). Component
rendering and the live drag/propose flow are verified in a browser (frontend
phase F-H).

## Layout

- `src/api/` — typed client + JSON types mirroring `app/results.py`. A workflow
  failure is a 200 with a `reason_code` (inspect it); `ApiError` is for 401/409/
  422/transport faults.
- `src/auth/` — login redirect + logout (the session is the backend's).
- `src/components/` — shared UI (the Loop topbar).
- `src/screens/` — one module per surface (onboarding, generation, schedule
  review, approval, today, accountability, thresholds).
- `src/lib/` — pure, unit-tested logic (tz/week math, approval helpers).
- `src/styles/tokens.css` — the design palette/typography, made responsive.

## Security note

`npm audit` flags the esbuild dev-server advisory (GHSA-67mh-4wv8-2f99) via
Vite 5 (and, transitively, vitest's vite-node/@vitest/mocker — npm's
"critical/high" counts are its aggregation of that single chain). It is
**dev-server only** — it lets a website reach a *running* `npm run dev` server —
and does not affect the production build (static assets the backend serves; F-H)
or test tooling output. The only fix is a major Vite bump, deliberately deferred.
Don't expose `npm run dev` to untrusted networks.
