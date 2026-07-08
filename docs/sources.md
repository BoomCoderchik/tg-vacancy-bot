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

- JobSpy LinkedIn
  - Enabled with `ENABLE_JOBSPY_LINKEDIN=true`; disabled by default.
  - Uses `python-jobspy` with `site_name="linkedin"`.
  - Query configured by `JOBSPY_LINKEDIN_QUERY`, `JOBSPY_LINKEDIN_LOCATION`, `JOBSPY_LINKEDIN_RESULTS_WANTED`, and `JOBSPY_LINKEDIN_HOURS_OLD`.
  - `JOBSPY_LINKEDIN_FETCH_DESCRIPTION=false` publishes lightweight link cards from search results; `true` lets JobSpy request individual LinkedIn job pages for descriptions.
  - Optional `JOBSPY_LINKEDIN_PROXIES` is passed through to JobSpy as a comma-separated proxy list.
  - Publication date: parsed from JobSpy `date_posted` when present.

## Intake Sources

- Direct or forwarded Telegram messages to the bot.
- Public Telegram channel origins when Telegram exposes forward metadata.
- LinkedIn URLs supplied manually by an operator via sent or forwarded vacancy text.
- LinkedIn links discovered by the opt-in JobSpy LinkedIn source.

## LinkedIn Boundary

The only automatic LinkedIn source is `JobSpyLinkedInAdapter`, and it must remain explicitly opt-in. Browser automation, account-based crawling, fake LinkedIn fallback rows, and undocumented LinkedIn scraping paths remain out of scope.

## Planned Source Pattern

New sources should be added as `SourceAdapter` implementations under `tg_vacancy_bot/sources/adapters/` and registered in `tg_vacancy_bot/sources/registry.py`.

Each adapter should:

- Call a real documented API/feed/page where automated access is allowed.
- For LinkedIn, use only the documented JobSpy adapter path unless project instructions are changed again.
- Return `Vacancy` objects.
- Use timeouts.
- Let the polling layer handle exceptions.
- Avoid fake fallback records.
- Add tests for adapter registration, filtering, or response mapping.
