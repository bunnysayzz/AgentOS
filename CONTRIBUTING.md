# Contributing to AgentOS Studio

Thanks for wanting to help. AgentOS Studio is a self-hosted, bring-your-own-key
control plane for AI agents, and every contribution counts — docs, bug reports,
UI polish, and code.

## Ground rules

- Be respectful. All interaction is covered by the [Code of Conduct](CODE_OF_CONDUCT.md).
- Keep changes focused. One logical change per pull request makes review fast and safe.
- Don't commit secrets. Keys live in environment variables; `.env` files are ignored.
- If you change behavior, update or add tests. The project treats the test suite as the contract.

## Local setup

Prereqs: Python 3.11+, Node 20+, and a Firebase project with Firestore + Auth.

```bash
# Backend (terminal 1)
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # fill in SECRET_KEY, ENCRYPTION_KEY, Firebase keys
uvicorn app.main:app --reload --port 8000

# Frontend (terminal 2)
cd frontend
npm install
cp .env.example .env            # fill in VITE_API_URL + Firebase web config
npm run dev                     # → http://localhost:5173
```

`make install`, `make dev-backend`, and `make dev-frontend` are shortcuts.

## Before you open a PR

Run the checks that CI runs:

```bash
make test                        # backend + frontend suites

# Backend
cd backend && ruff check app tests && pytest -q

# Frontend
cd frontend && npm run typecheck && npm run lint && npm test && npm run build
```

If your change touches UI, include a short description of what changed visually —
and a screenshot if it's more than a one-line tweak.

## How to contribute

1. Fork the repository and create a branch: `git checkout -b fix/describe-the-fix`.
2. Make your change, keeping it scoped to one concern.
3. Run the checks above; fix anything they flag.
4. Open a pull request against `main` using [the template](.github/PULL_REQUEST_TEMPLATE.md).

## Finding something to work on

- Check the open [issues](https://github.com/bunnysayzz/AgentOS/issues) for `good first issue`.
- The [README](README.md) roadmap tracks what's planned.
- [ARCHITECTURE.md](ARCHITECTURE.md) explains how the pieces fit together.

## Reporting problems

Found a bug or a security concern? See [SECURITY.md](SECURITY.md) — security
issues should be reported privately rather than as public issues.
