<div align="center">

# 🤖 AgentOS Studio

**Production-grade IDE for building, testing, deploying, and monitoring Agentic AI Systems**

[![CI](https://github.com/bunnysayzz/AgentOS/actions/workflows/ci.yml/badge.svg)](https://github.com/bunnysayzz/AgentOS/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.12](https://img.shields.io/badge/Python-3.12-blue.svg)](backend/pyproject.toml)
[![React 18](https://img.shields.io/badge/React-18-61dafb.svg)](frontend/package.json)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg)](backend/requirements.txt)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-18-336791.svg)](#database)

</div>

AgentOS Studio is a full-stack AI agent orchestration platform. It gives you a unified workspace to create, manage, version, and monitor **AI agents, workflows, tools, prompts, secrets, artifacts, and memory** — with multi-tenant workspace isolation, MCP gateway routing, telemetry, and execution tracing.

---

## ✨ Features

| | |
|---|---|
| 🤖 **Agent Management** | Create agents with configurable models & system prompts; full lifecycle (start / pause / resume / cancel) |
| ⚡ **Workflow Automation** | Sequential & approval-based workflows with manual/triggered execution |
| 🧠 **Memory Engine** | Session-based persistent memory with search, consolidation & importance scoring |
| 🔧 **Tool Registry** | Versioned tool definitions (functions, APIs, code) with public/workspace visibility |
| 📝 **Prompt Registry** | Version-controlled prompts with variable rendering & rollback |
| 🔐 **Secrets Manager** | Encrypted credential storage, per workspace & environment-scoped |
| 📦 **Artifact Store** | Versioned binary/structured asset tracking with content-type filtering |
| 🔌 **MCP Gateway** | LLM model routing with cost tracking, usage analytics & live chat completions |
| 📊 **Telemetry & Audit** | Event logging, audit trails, cost dashboards & duration analytics |
| 🔀 **Execution Graphs** | Node-level execution tracing & debugging for agent/workflow runs |
| 👥 **Workspace Isolation** | Multi-tenant workspaces with role-based access (Owner / Admin / Member / Viewer) |

> 📖 Full architecture walkthrough (API map, data model, state machines, auth flow): **[ARCHITECTURE.md](ARCHITECTURE.md)**

---

## 🧱 Tech Stack

- **Backend:** Python 3.12 · FastAPI · SQLAlchemy 2 (async) · Alembic · JWT auth (bcrypt) · OpenTelemetry
- **Frontend:** React 18 · TypeScript · Vite · Tailwind CSS · Zustand · TanStack Query · Axios
- **Database:** PostgreSQL (Aiven cloud) · SQLite (in-memory for tests)
- **Testing:** pytest (224 tests) · Vitest (38 tests) · Playwright E2E (5 tests) · GitHub Actions CI
- **Infra:** Docker · Render Blueprint (render.yaml)

---

## 🚀 Quick Start (Local Development)

### Prerequisites

- Python 3.11+
- Node.js 20+
- PostgreSQL 14+ (or use the Aiven cloud DB — see [Database](#database))

### 1. Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Configure environment
cp .env.example .env          # then fill in DATABASE_URL, SECRET_KEY, Firebase keys

# Run migrations & start the API
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 2. Frontend

```bash
cd frontend
npm install

# Configure environment
cp .env.example .env          # then fill in VITE_API_URL and Firebase web config

npm run dev                   # → http://localhost:5173
```

> Tip: use the `Makefile` shortcuts — `make dev-backend`, `make dev-frontend`, or `make install`.

---

## 🗄️ Environment Variables

### Backend (`backend/.env`)

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | ✅ | Async SQLAlchemy URL, e.g. `postgresql+asyncpg://user:pass@host:5432/db?ssl=require` |
| `SECRET_KEY` | ✅ | JWT signing secret (generate with `python -c "import secrets; print(secrets.token_urlsafe(32))"`) |
| `ENCRYPTION_KEY` | ✅ | Secret-encryption key (32+ bytes) |
| `CORS_ORIGINS` | | JSON list of allowed frontend origins |
| `FIREBASE_PROJECT_ID` | | Firebase project (defaults to `agentos-7f01e`) |
| `FIREBASE_CLIENT_EMAIL` / `FIREBASE_PRIVATE_KEY` | | Firebase service-account (production Firestore sync) |
| `FIREBASE_REFRESH_TOKEN` / `FIREBASE_CLIENT_ID` | | Firebase CLI OAuth fallback (local dev) |
| `FIRST_SUPERUSER_EMAIL` / `FIRST_SUPERUSER_PASSWORD` | | Auto-create an admin on first boot |

### Frontend (`frontend/.env`)

| Variable | Required | Description |
|---|---|---|
| `VITE_API_URL` | ✅ | Backend base URL, e.g. `http://localhost:8000/api/v1` (dev) or `https://agentos-backend.onrender.com/api/v1` (prod) |
| `VITE_FIREBASE_API_KEY` | ✅ | Firebase web API key |
| `VITE_FIREBASE_AUTH_DOMAIN` | ✅ | e.g. `your-project.firebaseapp.com` |
| `VITE_FIREBASE_PROJECT_ID` | ✅ | Firebase project ID |
| `VITE_FIREBASE_STORAGE_BUCKET` | ✅ | e.g. `your-project.appspot.com` |
| `VITE_FIREBASE_MESSAGING_SENDER_ID` | ✅ | Firebase sender ID |
| `VITE_FIREBASE_APP_ID` | ✅ | Firebase web app ID |

---

## 🧪 Testing

Run the **entire** pipeline (backend + frontend + E2E) with one command:

```bash
make test            # or: ./scripts/run_all_tests.sh
```

| Suite | Command | Count |
|---|---|---|
| Backend (pytest) | `cd backend && pytest -q` | 224 tests |
| Frontend typecheck | `cd frontend && npm run typecheck` | — |
| Frontend lint | `cd frontend && npm run lint` | — |
| Frontend unit (Vitest) | `cd frontend && npm test` | 38 tests |
| E2E (Playwright) | `cd frontend && npx playwright test` | 5 tests |

> Backend tests run against an in-memory SQLite database — they never touch your real data. The full pipeline is also enforced in CI (`.github/workflows/ci.yml`).

---

## ☁️ Deploy on Render

The repo ships with a [**Render Blueprint**](render.yaml) — deployment is one click, and **everything lives on a single URL**:

| Path | What it serves |
|---|---|
| `/` | The main React app (frontend) |
| `/admin` | Backend admin console — interactive API docs (Swagger UI) |
| `/api/v1/*` | The backend API |
| `/health` | Health check |

1. Push this repo to GitHub (it already is: `bunnysayzz/AgentOS`).
2. In [Render](https://render.com), click **New + → Blueprint** and select the repo.
3. Render auto-detects `render.yaml` and creates **one web service** (`agentos`). The build command installs the backend deps **and** builds the frontend (`npm ci && npm run build`), and FastAPI serves the SPA at the root.
4. Fill in the secret env vars the blueprint asks for (`sync: false` fields):
   - `DATABASE_URL` → your Aiven Postgres URI
   - `SECRET_KEY`, `ENCRYPTION_KEY` → generate strong random values
   - `FIREBASE_*` backend + `VITE_FIREBASE_*` frontend → your Firebase config
5. Deploy. Migrations run automatically on start (`alembic upgrade head`).

### Notes for Render

- **Free tier** spins down web services after 15 min of inactivity (first request after idle takes ~30–50 s).
- Because the SPA is served same-origin with the API, `VITE_API_URL=/api/v1` needs no CORS configuration.
- The backend needs no Redis to run — Redis/Celery are optional and only used when configured.

### Deploy with Docker instead

```bash
docker-compose up --build    # backend + frontend + postgres + redis
```

---

## 📁 Project Structure

```
AgentOS/
├── backend/                    # FastAPI backend
│   ├── app/
│   │   ├── api/                # Route handlers (auth, workspaces, agents, workflows, …)
│   │   ├── core/               # Config, database, security, firebase
│   │   ├── models/             # SQLAlchemy ORM models (21 tables)
│   │   ├── schemas/            # Pydantic request/response models
│   │   ├── services/           # Business logic
│   │   └── main.py             # App entry point
│   ├── alembic/                # Database migrations
│   └── tests/                  # 224 pytest tests
├── frontend/                   # React + Vite frontend
│   ├── src/
│   │   ├── components/         # Shared UI components
│   │   ├── pages/              # 15 route pages
│   │   ├── services/           # Axios API client + Firebase
│   │   ├── stores/             # Zustand stores (auth, ui, workspace)
│   │   └── utils/
│   ├── e2e/                    # Playwright smoke tests
│   └── src/**/*.test.*         # Vitest suites (38 tests)
├── .github/workflows/ci.yml    # CI pipeline
├── render.yaml                 # Render Blueprint
├── docker-compose.yml
├── Makefile
└── scripts/run_all_tests.sh    # Full test orchestrator
```

---

## 🤝 Contributing

1. Fork the repo.
2. Create a feature branch (`git checkout -b feat/my-feature`).
3. Run the full test suite (`make test`) and make sure everything is green.
4. Open a pull request.

---

## 📄 License

[MIT](LICENSE) © bunnysayzz
