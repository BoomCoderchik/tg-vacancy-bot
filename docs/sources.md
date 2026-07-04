# Sources

## Implemented

- Remotive API
  - Enabled with `ENABLE_REMOTIVE=true`.
  - No key required.
  - Publication date: parsed from `publication_date` when present.

- Arbeitnow API
  - Enabled with `ENABLE_ARBEITNOW=true`.
  - No key required.
  - Publication date: parsed from `created_at` when present.

- RemoteOK API
  - Enabled with `ENABLE_REMOTEOK=true`.
  - No key required.
  - Publication date: parsed from `date` or `epoch` when present.

- Hacker News "Who is Hiring"
  - Enabled with `ENABLE_HN_WHO_IS_HIRING=true`.
  - Uses Algolia HN API to locate the latest thread and parse candidate comments.
  - Publication date: parsed from comment timestamp fields when present.

- Adzuna API
  - Enabled only when `ADZUNA_APP_ID` and `ADZUNA_APP_KEY` are set.
  - Query configured by `ADZUNA_COUNTRY`, `ADZUNA_QUERY`, and `ADZUNA_LOCATION`.
  - Publication date: parsed from `created` when present.

- Jooble API
  - Enabled only when `JOOBLE_API_KEY` is set.
  - Query configured by `JOOBLE_KEYWORDS` and `JOOBLE_LOCATION`.
  - Publication date: parsed from `updated` when present.

## Intake Sources

- Direct or forwarded Telegram messages to the bot.
- Public Telegram channel origins when Telegram exposes forward metadata.
- LinkedIn URLs only when supplied by the user via a message or forwarded text.

## Planned Source Pattern

New sources should be added as `SourceAdapter` implementations under `tg_vacancy_bot/sources/adapters/` and registered in `tg_vacancy_bot/sources/registry.py`.

Each adapter should:

- Call a real documented API/feed/page where automated access is allowed.
- Return `Vacancy` objects.
- Use timeouts.
- Let the polling layer handle exceptions.
- Avoid fake fallback records.
- Add tests for adapter registration, filtering, or response mapping.
