# syntax=docker/dockerfile:1
# Single-instance image for the hosted multi-user web app.
#
# Multi-stage: build the React SPA, then serve it + the static landing from the
# Python app (server:create_hosted_app). The build context is the REPO ROOT
# (the image needs frontend/ and landing/, which are siblings of backend/), so
# build/deploy from the repo root and point at this Dockerfile:
#
#   docker build -t agentic-calendar -f backend/Dockerfile .
#   fly deploy            # fly.toml at the repo root sets the same context

# --- Stage 1: build the SPA -> /fe/dist -----------------------------------
FROM node:20-slim AS frontend
WORKDIR /fe
# Copy manifests first so `npm ci` is cached until the lockfile changes.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# --- Stage 2: the Python app + static assets ------------------------------
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    SPA_DIST_DIR=/app/frontend/dist \
    LANDING_INDEX=/app/landing/index.html

RUN pip install --no-cache-dir uv

WORKDIR /app
COPY backend/ /app
# Runtime deps only (no dev/test extras). Bundles fastapi/uvicorn/etc.
RUN uv sync --no-dev --frozen

# The static surfaces the hosted server serves: the landing page at "/" and the
# built SPA (index.html fallback for app routes, hashed bundles under /assets).
# SPA_DIST_DIR / LANDING_INDEX (above) point the server at these paths.
COPY landing/ /app/landing
COPY --from=frontend /fe/dist /app/frontend/dist

EXPOSE 8000

# Single process on purpose: SQLite + WAL is a one-process store, so do NOT add
# --workers. Mount a persistent volume for SHARED_DB_PATH and back it up (it
# holds personal data + encrypted tokens). All secrets arrive via env at run.
CMD ["uv", "run", "uvicorn", "agentic_calendar.app.web.server:create_hosted_app", \
     "--factory", "--host", "0.0.0.0", "--port", "8000"]
