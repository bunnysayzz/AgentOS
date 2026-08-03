# ─────────────────────────────────────────────────────────────────────────────
# AgentOS Studio — Single-service image
# ─────────────────────────────────────────────────────────────────────────────
# One container hosts BOTH the React app and the FastAPI backend, so a single
# URL serves everything:
#
#   /            → main React app (SPA, with client-side-route fallback)
#   /admin       → backend admin console (Swagger UI)
#   /api/v1/*    → backend API
#   /health      → health check
#
# Used by:
#   • Render "Web Service" deploys — Render auto-detects this root Dockerfile
#   • Render Blueprint deploys when configured with `env: docker`
#   • Local:  docker build -t agentos . && docker run -p 8000:8000 agentos
#
# Expected layout inside the image (matches backend's FRONTEND_DIST default):
#   /srv/backend          → FastAPI app        (WORKDIR)
#   /srv/frontend/dist    → built React SPA    (served at /)
# ─────────────────────────────────────────────────────────────────────────────

# ─── Stage 1: Build the React frontend ──────────────────────────────────────
FROM node:22-alpine AS frontend-build

WORKDIR /app/frontend

# Same-origin by design: the backend serves the SPA, so a relative base URL
# needs no CORS. Override at build time if ever needed:
#   docker build --build-arg VITE_API_URL=https://api.example.com/api/v1 .
ARG VITE_API_URL=/api/v1
ENV VITE_API_URL=$VITE_API_URL

# Optional Firebase web config — enables Google Sign-In. Vite inlines these
# at build time, so pass them as build args when needed (defaults are empty,
# which the app handles gracefully):
#   docker build \
#     --build-arg VITE_FIREBASE_API_KEY=... \
#     --build-arg VITE_FIREBASE_AUTH_DOMAIN=... \
#     --build-arg VITE_FIREBASE_PROJECT_ID=... \
#     --build-arg VITE_FIREBASE_STORAGE_BUCKET=... \
#     --build-arg VITE_FIREBASE_MESSAGING_SENDER_ID=... \
#     --build-arg VITE_FIREBASE_APP_ID=... .
ARG VITE_FIREBASE_API_KEY=
ARG VITE_FIREBASE_AUTH_DOMAIN=
ARG VITE_FIREBASE_PROJECT_ID=
ARG VITE_FIREBASE_STORAGE_BUCKET=
ARG VITE_FIREBASE_MESSAGING_SENDER_ID=
ARG VITE_FIREBASE_APP_ID=
ENV VITE_FIREBASE_API_KEY=$VITE_FIREBASE_API_KEY \
    VITE_FIREBASE_AUTH_DOMAIN=$VITE_FIREBASE_AUTH_DOMAIN \
    VITE_FIREBASE_PROJECT_ID=$VITE_FIREBASE_PROJECT_ID \
    VITE_FIREBASE_STORAGE_BUCKET=$VITE_FIREBASE_STORAGE_BUCKET \
    VITE_FIREBASE_MESSAGING_SENDER_ID=$VITE_FIREBASE_MESSAGING_SENDER_ID \
    VITE_FIREBASE_APP_ID=$VITE_FIREBASE_APP_ID

# Install deps from the lockfile (reproducible)
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

# Build the production bundle
COPY frontend/ ./
RUN npm run build

# ─── Stage 2: Python runtime (API + SPA hosting) ────────────────────────────
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /srv

# Build toolchain for packages that compile C extensions
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Backend dependencies (cached layer)
COPY backend/requirements.txt /srv/backend/requirements.txt
RUN pip install --no-cache-dir -r /srv/backend/requirements.txt

# Backend application code + entrypoint
COPY backend/ /srv/backend/

# Built SPA at the path the backend expects (repo_root/frontend/dist)
COPY --from=frontend-build /app/frontend/dist /srv/frontend/dist

WORKDIR /srv/backend
RUN chmod +x entrypoint.sh

EXPOSE 8000

# Starts uvicorn (see backend/entrypoint.sh). Data lives in Cloud Firestore
# — no SQL database, no migrations.
ENTRYPOINT ["./entrypoint.sh"]
