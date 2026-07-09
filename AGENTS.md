# Project Agent Instructions

This project is a real Telegram vacancy aggregator.

Before changing code, read:

- `README.md`
- `docs/architecture.md`
- `docs/sources.md`
- `docs/git-workflow.md`

Follow `docs/git-workflow.md` for every feature or code/documentation change.
Each completed feature or change must be committed after verification, and the
finished task branch must be pushed to GitHub unless pushing is impossible and
the blocker is reported clearly.

Required integrations must remain real. Do not add mock Telegram publishing, fake job source results, in-memory demo fallbacks, or placeholder vacancies unless the user explicitly asks for them.

When adding a source:

- Prefer official APIs, RSS feeds, or explicitly allowed public endpoints.
- Add a `SourceAdapter`.
- Normalize into `Vacancy`.
- Preserve deduplication.
- Add focused tests.
- Document required env variables or access.

LinkedIn automation must stay opt-in and documented. Do not add account login flows or fake LinkedIn results.
