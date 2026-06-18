# Single-instance image for the hosted multi-user web app.
# Build context is backend/:  docker build -t agentic-calendar backend/
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy

RUN pip install --no-cache-dir uv

WORKDIR /app
COPY . /app

# Runtime deps only (no dev/test extras). Bundles fastapi/uvicorn/jinja2/etc.
RUN uv sync --no-dev --frozen

EXPOSE 8000

# Single process on purpose: SQLite + WAL is a one-process store, so do NOT add
# --workers. Mount a persistent volume for SHARED_DB_PATH and back it up (it
# holds personal data + encrypted tokens). All secrets arrive via env at run.
CMD ["uv", "run", "uvicorn", "agentic_calendar.app.web.server:create_hosted_app", \
     "--factory", "--host", "0.0.0.0", "--port", "8000"]
