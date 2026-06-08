# ─────────────────────────────────────────────────────────────────────────────
# Lumen Health Backend — Production Dockerfile
#
# Build context  : backend/   (render.yaml: dockerContext: backend)
#   All COPY paths below are relative to backend/:
#     COPY requirements.txt ./  →  backend/requirements.txt        ✓
#     COPY . ./backend/         →  backend/* → /app/backend/*      ✓
#
# dockerfilePath : backend/Dockerfile  (render.yaml: relative to repo root)
#   Render resolves dockerfilePath from the REPOSITORY root, not from
#   dockerContext.  "Dockerfile" alone would give "no such file" — must be
#   "backend/Dockerfile".
#
# Runtime import resolution  (why the CMD uses "backend.app.main:app"):
#   Every source file uses absolute imports: "from backend.XXX import …"
#   This requires "backend" to be a package visible on sys.path.
#   Layout inside the container:
#     WORKDIR  /app               →  /app added to sys.path by Python/gunicorn
#     COPY . ./backend/           →  /app/backend/__init__.py   ✓
#                                    /app/backend/app/main.py   ✓
#                                    /app/backend/database.py   ✓
#   Therefore "backend.app.main" resolves to /app/backend/app/main.py  ✓
#   Switching to "app.main:app" would require /app/app/main.py which does
#   NOT exist and would crash with ModuleNotFoundError on every worker start.
#
# Base image : python:3.11-slim  (minimal Debian; no dev tools)
# Server     : gunicorn + UvicornWorker  (production-grade ASGI)
# Security   : non-root user, no secrets baked in — all secrets via env vars
# ─────────────────────────────────────────────────────────────────────────────

FROM python:3.11-slim AS base

# ── System dependencies ───────────────────────────────────────────────────────
# libpq-dev required for psycopg2-binary to link against at runtime on slim
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq5 \
    && rm -rf /var/lib/apt/lists/*

# ── Non-root user ─────────────────────────────────────────────────────────────
RUN addgroup --system dtx && adduser --system --ingroup dtx dtxuser

# ── Working directory ─────────────────────────────────────────────────────────
WORKDIR /app

# ── Python dependencies (install before copying app code for layer caching) ──
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

# ── Application source ────────────────────────────────────────────────────────
# Build context is backend/, so "." is the backend directory.
# Copying into /app/backend/ preserves the "backend.app.main" import path:
#   WORKDIR /app  +  /app/backend/app/main.py  →  gunicorn backend.app.main:app
COPY . ./backend/

# ── Ownership ────────────────────────────────────────────────────────────────
RUN chown -R dtxuser:dtx /app
USER dtxuser

# ── Runtime configuration ─────────────────────────────────────────────────────
# PORT is injected by Render (default 8000 for local runs)
ENV PORT=8000 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE ${PORT}

# ── Entrypoint ────────────────────────────────────────────────────────────────
# • 2 workers per container (Render free tier is single-CPU; adjust via $WEB_CONCURRENCY)
# • UvicornWorker bridges gunicorn's sync process model with FastAPI's async handlers
# • --bind 0.0.0.0:$PORT listens on all interfaces (required for Render's proxy)
# • --access-logfile - streams access logs to stdout (Render captures them)
CMD gunicorn backend.app.main:app \
      --worker-class uvicorn.workers.UvicornWorker \
      --workers ${WEB_CONCURRENCY:-2} \
      --bind "0.0.0.0:${PORT}" \
      --access-logfile - \
      --error-logfile - \
      --log-level info \
      --timeout 120
