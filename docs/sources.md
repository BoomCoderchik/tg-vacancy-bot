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

- LinkedIn Hiring Posts
  - Enabled only when `ENABLE_LINKEDIN_POST_SEARCH=true` and `SERPAPI_API_KEY` or `SERPER_API_KEY` are set.
  - Uses SerpApi Google Search (`https://serpapi.com/search.json`) or Serper Google Search (`https://google.serper.dev/search`) to find publicly indexed LinkedIn post URLs, not LinkedIn Jobs pages.
  - Searches globally indexed posts; query configured by `LINKEDIN_POST_SEARCH_QUERY` and `LINKEDIN_POST_SEARCH_RESULTS_WANTED`; separate fallback search queries with `||`.
  - Maps search `title`, `snippet`, `link`, and date into a short `Vacancy` card with source `LinkedIn Hiring Posts`. A reliable date is required and posts older than `LINKEDIN_POST_MAX_AGE_HOURS` (at most 120 hours) are rejected. Hashtag-heavy search titles are normalized into the detected role when the role is present in the title or snippet.
  - Drops results that are not `linkedin.com/posts/...` or `linkedin.com/feed/update/...`.

- LinkedIn Hiring Post Scraper
  - Enabled with `ENABLE_LINKEDIN_POST_SCRAPER=true`.
  - Scrapes public search-result HTML to find publicly indexed LinkedIn post URLs, not LinkedIn Jobs pages.
  - Uses the configured `LINKEDIN_POST_SCRAPER_SEARCH_PROVIDERS` list, defaulting to `duckduckgo,bing`, so a DuckDuckGo anti-bot challenge does not stop the whole source while another public HTML provider is available.
  - Requires a publication date: it reads a date exposed by the search result or derives it from the LinkedIn `activity-...` ID. Results without a reliable date and posts older than `LINKEDIN_POST_MAX_AGE_HOURS` (at most 120 hours) are skipped.
  - Searches globally indexed posts; query configured by `LINKEDIN_POST_SCRAPER_QUERY`, `LINKEDIN_POST_SCRAPER_SEARCH_PROVIDERS`, and `LINKEDIN_POST_SCRAPER_RESULTS_WANTED`; separate fallback search queries with `||`.
  - The default search depth is 100 candidates. This is a collection limit, not a publication limit; source polling and SQLite deduplication publish the candidates in later safe batches.
  - Maps result title, snippet, and link into a short `Vacancy` card with source `LinkedIn Hiring Post Scraper`.
  - Hashtag-heavy search titles are normalized into the detected role when the role is present in the title or snippet.
  - Drops results that are not `linkedin.com/posts/...` or `linkedin.com/feed/update/...`.
  - Requires no API key, but can return no rows if search-result markup changes or the search provider rate-limits requests.

- LinkedIn Hiring Posts (Headless)
  - Enabled with `ENABLE_LINKEDIN_POST_HEADLESS=true`; disabled by default.
  - Uses SerpApi or Serper, when their existing key is configured, to discover public LinkedIn post URLs, then opens those URLs in a clean Playwright browser context. Without a search-provider key it uses Bing discovery as a best-effort fallback, which can return no rows when blocked.
  - Searches globally indexed posts; query configured by `LINKEDIN_POST_HEADLESS_QUERY`, `LINKEDIN_POST_HEADLESS_RESULTS_WANTED`, and `LINKEDIN_POST_HEADLESS_TIMEOUT_SECONDS`.
  - Does not use a LinkedIn account, cookies, proxies, identity masking, or protection bypasses. Pages that require login or show CAPTCHA/2FA are skipped.
  - Requires text in a public post container, derives the publication date from the LinkedIn activity ID, and rejects posts older than `LINKEDIN_POST_MAX_AGE_HOURS` (at most 120 hours); otherwise it does not create a vacancy.

## Intake Sources

- Direct or forwarded Telegram messages to the bot.
- Public Telegram channel origins when Telegram exposes forward metadata.
- LinkedIn URLs supplied manually by an operator via sent or forwarded vacancy text.
- LinkedIn post links discovered by the opt-in SerpApi-backed or Serper-backed hiring-post search source.
- LinkedIn post links discovered by the opt-in free hiring-post scraper source.
- LinkedIn post links and descriptions discovered by the opt-in headless source.

## LinkedIn Boundary

The four automatic LinkedIn adapters are `LinkedInPostSearchAdapter` for SerpApi-backed public hiring posts, `LinkedInPostSerperAdapter` for Serper-backed public hiring posts, `LinkedInPostScraperAdapter` for free public search-result scraping, and `LinkedInPostHeadlessAdapter` for public post pages opened without login. The headless adapter reuses SerpApi or Serper for reliable URL discovery when configured, with Bing only as a best-effort no-key fallback. They must remain explicitly opt-in. Account-based crawling, proxy use, protection bypasses, and fake LinkedIn fallback rows remain out of scope.

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
