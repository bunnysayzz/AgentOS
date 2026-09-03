# Governance

AgentOS Studio is a small, community-driven open source project. This document
describes how decisions get made so contributors know what to expect. It is a
living document — open an issue or pull request if you think a process should
change.

## Maintainers

The project is maintained by the repository owner (bunnysayzz) plus any
contributors who have earned merge access by landing consistent, high-quality
changes. Current maintainers are listed on the repository's members page.

Maintainers are responsible for:

- Reviewing and merging pull requests
- Triaging issues and keeping the roadmap honest
- Cutting releases and tagging versions
- Enforcing the [Code of Conduct](CODE_OF_CONDUCT.md)
- Responding to [security reports](SECURITY.md)

## Decision process

Decisions are made by consensus among maintainers, with the project owner
holding final say. In practice, for a project this size:

- **Small, unambiguous fixes and polish** — merged after review and green CI.
- **New features** — discussed first as an issue so the design is agreed before
  code lands. Big features should include a short proposal: the problem, the
  approach, and what changes.
- **API or data-model changes** — treated like features but with extra care.
  Breaking changes require a migration note and a version bump.
- **License, governance, or scope changes** — surfaced to the whole community
  through an issue and given time for discussion before a decision.

If you disagree with a decision, say so respectfully on the issue or PR. Good
arguments with evidence change outcomes.

## Releases

Releases follow [Semantic Versioning](https://semver.org/):

- **Patch** — bug fixes and small polish
- **Minor** — backward-compatible features
- **Major** — breaking changes

Release notes summarize user-facing changes. Security fixes are backported only
to the latest major version, per [SECURITY.md](SECURITY.md).

## Contribution standards

Everything in [CONTRIBUTING.md](CONTRIBUTING.md) applies. Two rules carry extra
weight:

1. The test suite is the contract. Changes that break tests don't merge.
2. No secrets, ever. The CI secret scan enforces this automatically.

## Credits

AgentOS Studio is MIT licensed. Contributions remain owned by their authors and
are licensed to the project under the terms of the MIT license. Maintainers and
contributors are credited through the GitHub contributors graph.
