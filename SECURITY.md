# Security Policy

AgentOS Studio stores API keys, secrets, and workspace data, so we take
security reports seriously.

## Supported versions

Only the latest release on `main` receives security fixes. Old releases are not
maintained unless a version is explicitly marked as supported here.

## Reporting a vulnerability

Please do **not** open a public issue for security problems. Report them
privately through one of:

- GitHub private vulnerability reporting (Security tab → "Report a
  vulnerability") — preferred, if enabled for this repository
- A private issue in this repository with the `security` label, if private
  reporting is unavailable

Include, when possible:

- The affected component and version (commit hash is ideal)
- A short description of the issue and its impact
- Steps to reproduce, or a proof of concept
- Any suggested mitigation

You should get an acknowledgment within a few days. We ask that you give us
time to fix and release the issue before disclosing it publicly; coordinated
disclosure is appreciated.

## What we care about

- Exposure of stored secrets, API keys, or credentials
- Authentication or authorization bypass (including workspace and team scoping)
- Injection or code execution via agent content, tool output, or provider data
- Key or token leakage through logs, URLs, or error messages
- Data exfiltration from a self-hosted instance

## What is not in scope

- Issues in upstream dependencies (report to the dependency maintainer)
- Phishing or abuse of public demo instances
- Denial of service on your own self-hosted instance

## Security practices in this repo

- All secrets are environment variables; `.env*` files are gitignored
- Provider keys travel in headers, never in URLs
- Backend tests use an in-memory fake Firestore and never touch real data
