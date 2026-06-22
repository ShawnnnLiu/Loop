# Loop frontend

The hi-fi **Loop** product UI — a React + Vite + TypeScript SPA that is a thin
client of the FastAPI JSON API (`/api/*`) and the server-side Google OAuth flow
(`/auth/*`). No control-plane logic lives here: routing, validation, scheduling,
the approval gate, the payload-hash recheck, calendar writes, and verification
all stay server-side. The SPA renders state and sends intents.

See `docs/implementation-plans/phase-loop-mvp-frontend.md` for the full plan and
the commit breakdown (F-A…F-H).

## Develop

The dev server proxies `/api`, `/auth`, and `/healthz` to the backend, so run
the FastAPI app on `:8000` first (dev mode = no auth, a single configured user):

```bash
# terminal 1 — backend (from backend/), dev mode on :8000
cd ../backend && uv run uvicorn <composition-root app>:app --port 8000

# terminal 2 — frontend
npm install
npm run dev          # http://localhost:5173
```

In production the backend serves the built assets directly (frontend phase F-H);
there is no separate dev proxy then.

## Checks (the per-commit frontend gate)

```bash
npm run typecheck    # tsc --noEmit
npm run lint         # eslint
npm run build        # tsc --noEmit && vite build
```

## Layout

- `src/api/` — typed client + JSON types mirroring `app/results.py`. A workflow
  failure is a 200 with a `reason_code` (inspect it); `ApiError` is for 401/409/
  422/transport faults.
- `src/auth/` — login redirect + logout (the session is the backend's).
- `src/components/` — shared UI (the Loop topbar).
- `src/screens/` — one module per surface (placeholders until their commit).
- `src/styles/tokens.css` — the design palette/typography, made responsive.

## Security note

`npm audit` flags the esbuild dev-server advisory (GHSA-67mh-4wv8-2f99) via
Vite 5. It is **dev-server only** — it lets a website reach a *running* `npm run
dev` server — and does not affect the production build (static assets the
backend serves; F-H). The only fix is a major Vite bump, deliberately deferred
for a scaffold. Don't expose `npm run dev` to untrusted networks.
