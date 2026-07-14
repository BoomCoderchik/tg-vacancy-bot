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
  - Enabled with `ENABLE_JOBSPY_LINKEDIN=true`; disabled by default and should remain disabled when ordinary LinkedIn Jobs cards are out of scope.
  - Uses `python-jobspy` with `site_name="linkedin"`.
  - Query configured by `JOBSPY_LINKEDIN_QUERY`, `JOBSPY_LINKEDIN_LOCATION`, `JOBSPY_LINKEDIN_RESULTS_WANTED`, and `JOBSPY_LINKEDIN_HOURS_OLD`.
  - `JOBSPY_LINKEDIN_FETCH_DESCRIPTION=false` publishes lightweight link cards from search results; `true` lets JobSpy request individual LinkedIn job pages for descriptions.
  - Optional `JOBSPY_LINKEDIN_PROXIES` is passed through to JobSpy as a comma-separated proxy list.
  - Publication date: parsed from JobSpy `date_posted` when present.

- LinkedIn Hiring Posts
  - Enabled only when `ENABLE_LINKEDIN_POST_SEARCH=true` and `SERPAPI_API_KEY` or `SERPER_API_KEY` are set.
  - Uses SerpApi Google Search (`https://serpapi.com/search.json`) or Serper Google Search (`https://google.serper.dev/search`) to find publicly indexed LinkedIn post URLs, not LinkedIn Jobs pages.
  - Query configured by `LINKEDIN_POST_SEARCH_QUERY`, `LINKEDIN_POST_SEARCH_LOCATION`, and `LINKEDIN_POST_SEARCH_RESULTS_WANTED`; separate fallback search queries with `||`.
  - Maps search `title`, `snippet`, `link`, and optional `date` into a short `Vacancy` card with source `LinkedIn Hiring Posts`. Hashtag-heavy search titles are normalized into the detected role when the role is present in the title or snippet.
  - Drops results that are not `linkedin.com/posts/...` or `linkedin.com/feed/update/...`.

- LinkedIn Hiring Post Scraper
  - Enabled with `ENABLE_LINKEDIN_POST_SCRAPER=true`.
  - Scrapes public search-result HTML to find publicly indexed LinkedIn post URLs, not LinkedIn Jobs pages.
  - Uses the configured `LINKEDIN_POST_SCRAPER_SEARCH_PROVIDERS` list, defaulting to `duckduckgo,bing`, so a DuckDuckGo anti-bot challenge does not stop the whole source while another public HTML provider is available.
  - Requires a publication date: it reads a date exposed by the search result or derives it from the LinkedIn `activity-...` ID. Results without a reliable date are skipped, so old indexed posts are not published.
  - Query configured by `LINKEDIN_POST_SCRAPER_QUERY`, `LINKEDIN_POST_SCRAPER_LOCATION`, `LINKEDIN_POST_SCRAPER_SEARCH_PROVIDERS`, and `LINKEDIN_POST_SCRAPER_RESULTS_WANTED`; separate fallback search queries with `||`.
  - The default search depth is 100 candidates. This is a collection limit, not a publication limit; source polling and SQLite deduplication publish the candidates in later safe batches.
  - Maps result title, snippet, and link into a short `Vacancy` card with source `LinkedIn Hiring Post Scraper`.
  - Hashtag-heavy search titles are normalized into the detected role when the role is present in the title or snippet.
  - Drops results that are not `linkedin.com/posts/...` or `linkedin.com/feed/update/...`.
  - Requires no API key, but can return no rows if search-result markup changes or the search provider rate-limits requests.

## Intake Sources

- Direct or forwarded Telegram messages to the bot.
- Public Telegram channel origins when Telegram exposes forward metadata.
- LinkedIn URLs supplied manually by an operator via sent or forwarded vacancy text.
- LinkedIn links discovered by the opt-in JobSpy LinkedIn source.
- LinkedIn post links discovered by the opt-in SerpApi-backed or Serper-backed hiring-post search source.
- LinkedIn post links discovered by the opt-in free hiring-post scraper source.

## LinkedIn Boundary

The automatic LinkedIn sources are `LinkedInPostSearchAdapter` for SerpApi-backed public hiring posts, `LinkedInPostSerperAdapter` for Serper-backed public hiring posts, `LinkedInPostScraperAdapter` for free public search-result scraping, and `JobSpyLinkedInAdapter` for LinkedIn Jobs. They must remain explicitly opt-in. Account-based crawling and fake LinkedIn fallback rows remain out of scope.

## Planned Source Pattern

New sources should be added as `SourceAdapter` implementations under `tg_vacancy_bot/sources/adapters/` and registered in `tg_vacancy_bot/sources/registry.py`.

Each adapter should:

- Call a real documented API/feed/page where automated access is allowed.
- For LinkedIn, use documented opt-in adapters and do not invent fallback vacancies.
- Return `Vacancy` objects.
- Use timeouts.
- Let the polling layer handle exceptions.
- Avoid fake fallback records.
- Add tests for adapter registration, filtering, or response mapping.
