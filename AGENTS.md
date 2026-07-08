# Project Agent Instructions

This project is a real Telegram vacancy aggregator.

Before changing code, read:

- `README.md`
- `docs/architecture.md`
- `docs/sources.md`

Required integrations must remain real. Do not add mock Telegram publishing, fake job source results, in-memory demo fallbacks, or placeholder vacancies unless the user explicitly asks for them.

When adding a source:

- Prefer official APIs, RSS feeds, or explicitly allowed public endpoints.
- Add a `SourceAdapter`.
- Normalize into `Vacancy`.
- Preserve deduplication.
- Add focused tests.
- Document required env variables or access.

LinkedIn automation is allowed only through the documented, opt-in JobSpy LinkedIn source in this project. Do not add browser automation, account login flows, fake LinkedIn results, or undocumented LinkedIn scraping paths.
