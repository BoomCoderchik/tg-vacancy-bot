# Project Agent Instructions

This project is a real Telegram vacancy aggregator.

Before changing code, read:

- `README.md`
- `docs/architecture.md`
- `docs/sources.md`
- `docs/task-workflow.md`
- `docs/git-workflow.md`

Follow `docs/task-workflow.md` for the project task lifecycle: understand the
request, inspect context, plan when needed, implement narrowly, verify, review,
and report the result.

Follow `docs/git-workflow.md` for every feature or code/documentation change.
Each completed feature or change must be committed after verification, and the
finished task branch must be pushed to GitHub unless pushing is impossible and
the blocker is reported clearly.

## GitFlow

This project uses an adapted GitFlow process. `main` contains production-ready
code and `develop` is the normal integration branch. Start ordinary work from
`develop` on `feature/<short-name>` or `bugfix/<short-name>`. Use
`release/<version-or-date>` only for release stabilization and
`hotfix/<short-name>` only for urgent fixes from `main`.

The owner authorizes Codex to create, push, and merge verified GitFlow branches
when the documented flow calls for it. A verified feature or bugfix may merge
into `develop`; a verified release or hotfix may merge into `main` and must be
synced back into `develop`. Pull requests are optional unless requested by the
owner or required by GitHub branch protection. Never bypass protection rules or
merge unverified work.

Required integrations must remain real. Do not add mock Telegram publishing, fake job source results, in-memory demo fallbacks, or placeholder vacancies unless the user explicitly asks for them.

When adding a source:

- Prefer official APIs, RSS feeds, or explicitly allowed public endpoints.
- Add a `SourceAdapter`.
- Normalize into `Vacancy`.
- Preserve deduplication.
- Add focused tests.
- Document required env variables or access.

LinkedIn automation must stay opt-in and documented. Do not add account login flows or fake LinkedIn results.
