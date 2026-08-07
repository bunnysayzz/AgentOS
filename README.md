<div align="center">

[<img src="assets/banner.svg" alt="AgentOS Studio | Self-hosted agent studio. Your keys. Your data." width="100%" />](https://letsagentos.onrender.com)

<br />

[![Live demo](https://img.shields.io/badge/Try%20the%20live%20demo-letsagentos.onrender.com-e3b862.svg)](https://letsagentos.onrender.com)
[![CI](https://github.com/bunnysayzz/AgentOS/actions/workflows/ci.yml/badge.svg)](https://github.com/bunnysayzz/AgentOS/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

</div>

## Self-hosted agent studio. Your keys. Your data.

AgentOS Studio is a **bring-your-own-key** control plane for AI agents — the part of the stack that OpenAI's ChatGPT and hosted platforms keep locked in. Run it on your own infrastructure, connect your own LLM API keys, and get chat, agents, workflows, tools, secrets, and execution tracing in one deploy.

No per-seat pricing. No inference markup. No data leaving your infrastructure.

> ### 🔗 Try it live — no signup required
> [letsagentos.onrender.com](https://letsagentos.onrender.com) runs the real thing in guest mode. Explore every page, chat with a model, build an agent — nothing is locked behind a login wall.
> [Browse the community agent gallery](https://letsagentos.onrender.com/gallery) and clone a proven agent into your workspace with one click.

---

## The problem it solves

Building real AI agents means juggling a pile of disconnected pieces:

- **Scattered LLM keys** across developers, environments, and `.env` files nobody can audit
- **Prompt drift** — nobody knows which version of a prompt an agent ran last week
- **No visibility** into what an agent actually *did* (which tool, which call, how much it cost)
- **Reinventing the wheel** — every team rebuilds the same chat + agent + workflow plumbing
- **No safe way to share** an agent that works with someone else

AgentOS Studio turns that pile into one self-hosted control plane: **workspaces with real roles, versioned agents and prompts, an execution engine with approval gates, encrypted secrets, tool bindings, node-level tracing, and cost telemetry.**

## What's inside

| | |
|---|---|
| 🤖 **Agents** | Configurable models, system prompts, tool bindings, full lifecycle (start / pause / resume / cancel) |
| ⚡ **Workflows** | Sequential & approval-gated flows with manual / webhook / cron triggers |
| 💬 **Chat** | LLM chat completions through your own providers (OpenAI-compatible) |
| 🧠 **Memory** | Session-based persistent memory with search, consolidation & importance scoring |
| 🔧 **Tools** | Versioned tool definitions with per-agent binding |
| 📝 **Prompts** | Version-controlled prompt templates with variables & rollback |
| 🔐 **Secrets** | Encrypted credential storage, workspace & environment-scoped |
| 🔌 **MCP Gateway** | Model routing, usage analytics, and live completions |
| 🔀 **Execution Graphs** | Node-level execution tracing & debugging |
| 📊 **Telemetry** | Event logging, audit trails, cost & duration dashboards |
| 🌐 **Community Gallery** | Publish an agent, or clone one someone else built, with one click |
| 👥 **Workspaces** | Multi-tenant isolation with Owner / Admin / Member / Viewer roles |

> 📖 Full architecture walkthrough (API map, data model, state machines, auth flow): **[ARCHITECTURE.md](ARCHITECTURE.md)**

---

## Quick start (local dev)

**Prereqs:** Python 3.11+, Node 20+, and a Firebase project (Firestore + Auth). No SQL database needed — all data lives in Cloud Firestore.

```bash
# 1. Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # fill in SECRET_KEY, ENCRYPTION_KEY, Firebase keys
uvicorn app.main:app --reload --port 8000

# 2. Frontend (in a second terminal)
cd frontend
npm install
cp .env.example .env          # fill in VITE_API_URL + Firebase web config
npm run dev                   # → http://localhost:5173
```

> Tip: use the `Makefile` shortcuts — `make dev-backend`, `make dev-frontend`, or `make install`.

---

## Deploy on Render (one service, one URL)

The repo ships a [Render Blueprint](render.yaml) **and** a root [Dockerfile](Dockerfile). Either deploys in one click — the backend serves the built frontend, so **everything lives on a single URL**:

| Path | What it serves |
|---|---|
| `/` | The app (React frontend) |
| `/gallery` | Public community agent gallery |
| `/admin` | Backend admin console (interactive API docs) |
| `/api/v1/*` | The backend API |
| `/health` | Health check |

1. Push this repo to GitHub (already at `bunnysayzz/AgentOS`).
2. In Render: **New + → Blueprint** (recommended) and select the repo — or **New + → Web Service** and let it pick up the root `Dockerfile`.
3. Set the env vars: `SECRET_KEY`, `ENCRYPTION_KEY`, Firebase credentials, and the `VITE_FIREBASE_*` web config if you want Google Sign-In.
4. Deploy. **No database migrations** — everything is Cloud Firestore.

> **Free-tier note:** Render spins down free web services after ~15 min of inactivity; the first request after idle takes ~30–50 s to wake up.

---

## Environment variables

### Backend (`backend/.env`)

| Variable | Required | Description |
|---|---|---|
| `SECRET_KEY` | ✅ | JWT signing secret (`python -c "import secrets; print(secrets.token_urlsafe(32))"`) |
| `ENCRYPTION_KEY` | ✅ | Secret-encryption key (32+ bytes) |
| `CORS_ORIGINS` | | JSON list of allowed frontend origins |
| `FIREBASE_PROJECT_ID` | | Firebase project |
| `FIREBASE_CLIENT_EMAIL` / `FIREBASE_PRIVATE_KEY` | | Firebase service account (production Firestore access) |
| `FIREBASE_REFRESH_TOKEN` / `FIREBASE_CLIENT_ID` | | Firebase CLI OAuth fallback (local dev) |
| `FIRST_SUPERUSER_EMAIL` | | Email promoted to admin on first sign-in |

### Frontend (`frontend/.env`)

| Variable | Required | Description |
|---|---|---|
| `VITE_API_URL` | ✅ | Backend base URL (`http://localhost:8000/api/v1` dev, `/api/v1` prod) |
| `VITE_FIREBASE_API_KEY` | ⬜ | Firebase web API key — **optional**, only for Google Sign-In |
| `VITE_FIREBASE_AUTH_DOMAIN` | ⬜ | e.g. `your-project.firebaseapp.com` |
| `VITE_FIREBASE_PROJECT_ID` | ⬜ | Firebase project ID |
| `VITE_FIREBASE_STORAGE_BUCKET` | ⬜ | Firebase storage bucket |
| `VITE_FIREBASE_MESSAGING_SENDER_ID` | ⬜ | Firebase sender ID |
| `VITE_FIREBASE_APP_ID` | ⬜ | Firebase web app ID |

> Firebase is **optional**: email/password auth and the full agent engine work with zero Firebase config beyond Firestore itself. Google Sign-In activates only when the `VITE_FIREBASE_*` vars are present.

---

## Testing

```bash
make test   # backend + frontend + E2E
```

| Suite | Command | Count |
|---|---|---|
| Backend (pytest) | `cd backend && pytest -q` | 291 tests |
| Frontend unit (Vitest) | `cd frontend && npm test` | 98 tests |
| Frontend typecheck | `cd frontend && npm run typecheck` | — |
| Frontend lint | `cd frontend && npm run lint` | — |

Backend tests run against an in-memory fake Firestore — they never touch your real data. The full pipeline is enforced in CI (`.github/workflows/ci.yml`).

---

## Tech stack (for contributors)

- **Backend:** Python 3.12 · FastAPI · Firebase Auth · Cloud Firestore (no SQL)
- **Frontend:** React 18 · TypeScript · Vite · Tailwind CSS · Zustand · TanStack Query
- **Infra:** Docker · Render Blueprint · GitHub Actions CI
- **Observability:** Sentry (optional, env-gated) · privacy-friendly analytics (optional)

## Project structure

```
AgentOS/
├── backend/                 # FastAPI backend (api/, core/, schemas/, services/, tests/)
├── frontend/                # React + Vite frontend (components/, pages/, services/, stores/)
├── .github/workflows/ci.yml # CI pipeline
├── Dockerfile               # Single-service image (frontend + backend)
├── render.yaml              # Render Blueprint (one-click deploy)
├── assets/banner.svg        # Brand banner
└── Makefile                 # Dev & test shortcuts
```

---

## Roadmap

- [x] Agents, workflows, memory, tools, prompts, secrets, artifacts, MCP gateway, tracing, telemetry
- [x] Guest mode (no login wall) + community agent gallery
- [x] GDPR: account data export & deletion
- [ ] Agent evals & regression testing (trace-level scoring)
- [ ] Shared agent templates & one-click provider presets
- [ ] MCP server marketplace

## License

[MIT](LICENSE) © bunnysayzz
