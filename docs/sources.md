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

- Jobicy API
  - Enabled with `ENABLE_JOBICY=true`.
  - No key required.
  - Uses the public `https://jobicy.com/api/v2/remote-jobs?tag=dev` endpoint.
  - Publication date: parsed from `pubDate` when present.

- We Work Remotely Programming RSS
  - Enabled with `ENABLE_WE_WORK_REMOTELY=true`.
  - No key required.
  - Uses the public programming RSS feed.
  - Publication date: parsed from RSS `pubDate` when present.

- Himalayas RSS
  - Enabled with `ENABLE_HIMALAYAS=true`.
  - No key required.
  - Uses the public remote jobs RSS feed.
  - Publication date: parsed from RSS `pubDate` when present.

- Real Work From Anywhere RSS
  - Enabled with `ENABLE_REAL_WORK_FROM_ANYWHERE=true`.
  - No key required.
  - Uses the public remote jobs RSS feed.
  - Publication date: parsed from RSS `pubDate` when present.

- JobsCollider RSS
  - Enabled with `ENABLE_JOBSCOLLIDER=true`.
  - No key required.
  - Uses the public remote jobs RSS feed.
  - Publication date: parsed from RSS `pubDate` when present.

- Adzuna API
  - Enabled only when `ADZUNA_APP_ID` and `ADZUNA_APP_KEY` are set.
  - Query configured by `ADZUNA_COUNTRY`, `ADZUNA_QUERY`, and `ADZUNA_LOCATION`.
  - Publication date: parsed from `created` when present.

- Jooble API
  - Enabled only when `JOOBLE_API_KEY` is set.
  - Query configured by `JOOBLE_KEYWORDS` and `JOOBLE_LOCATION`.
  - Publication date: parsed from `updated` when present.

- LinkedIn user posts authorized JSON feed
  - Enabled only when `ENABLE_LINKEDIN_USER_POSTS=true` and `LINKEDIN_USER_POSTS_FEED_URL` is set.
  - The feed must be produced by an official API, webhook, export, or external service that is allowed to provide LinkedIn post data.
  - The adapter accepts a top-level JSON array, or an object with `posts`, `items`, `data`, or `results`.
  - Records should provide `url` or `link`, `text` or `content`, optional `published_at`, and optional `author`.
  - Publication date: parsed from `published_at`, `publishedAt`, `created_at`, `createdAt`, or `date` when present.
  - Filtering requires explicit hiring intent and an allowed developer/designer role.
  - Direct LinkedIn scraping and browser automation are intentionally not implemented.

- LinkedIn user posts inbound webhook
  - Enabled only when `LINKEDIN_USER_POSTS_WEBHOOK_TOKEN` is set and the app runs with `tg-vacancy-bot run-web`.
  - Accepts `POST /linkedin/user-posts` with `Authorization: Bearer <token>` or `X-Webhook-Token: <token>`.
  - The payload shape matches the authorized JSON feed and may also be a single post object.
  - Publishes accepted records immediately through the real Telegram publisher and the same SQLite deduplication store.
  - The upstream system must be an official API, webhook, export, or external service that is allowed to provide LinkedIn post data.

- LinkedIn Posts API
  - Enabled only when `LINKEDIN_API_ACCESS_TOKEN` and `LINKEDIN_API_AUTHOR_URNS` are set.
  - Uses the official `https://api.linkedin.com/rest/posts` endpoint with `q=author`.
  - `LINKEDIN_API_AUTHOR_URNS` is a comma- or semicolon-separated list of `urn:li:person:...` or `urn:li:organization:...` author URNs.
  - `LINKEDIN_API_VERSION` defaults to `202606`.
  - Requires LinkedIn-approved API access and the permissions LinkedIn requires for the configured authors.
  - Direct LinkedIn page scraping and browser automation remain intentionally out of scope.

## Intake Sources

- Direct or forwarded Telegram messages to the bot.
- Public Telegram channel origins when Telegram exposes forward metadata.
- LinkedIn URLs when supplied by the user via a message or forwarded text, or when provided by the authorized LinkedIn user-post JSON feed.
- LinkedIn user-post JSON pushed to `/linkedin/user-posts` by an authorized upstream provider.
- LinkedIn posts returned by the official LinkedIn Posts API for configured author URNs.

## Planned Source Pattern

New sources should be added as `SourceAdapter` implementations under `tg_vacancy_bot/sources/adapters/` and registered in `tg_vacancy_bot/sources/registry.py`.

Each adapter should:

- Call a real documented API/feed/page where automated access is allowed.
- Return `Vacancy` objects.
- Use timeouts.
- Let the polling layer handle exceptions.
- Avoid fake fallback records.
- Add tests for adapter registration, filtering, or response mapping.
