# Sources

## Active Sources

Automatic polling is limited to LinkedIn hiring posts.

- `LinkedInPostSearchAdapter`
  - Opt-in with `ENABLE_LINKEDIN_POST_SEARCH=true`.
  - Uses SerpApi when `SERPAPI_API_KEY` is set.
  - Reads only publicly indexed `linkedin.com/posts/...` and `linkedin.com/feed/update/...` results.

- `LinkedInPostSerperAdapter`
  - Opt-in with `ENABLE_LINKEDIN_POST_SEARCH=true`.
  - Uses Serper when `SERPER_API_KEY` is set.
  - Reads the same public LinkedIn post URL scope as the SerpApi adapter.

- `LinkedInPostScraperAdapter`
  - Opt-in with `ENABLE_LINKEDIN_POST_SCRAPER=true`.
  - Uses public search-result providers such as Bing RSS, DuckDuckGo, and Bing HTML.
  - Skips CAPTCHA, anti-bot, empty, or malformed provider responses instead of bypassing protection.

- `LinkedInPostHeadlessAdapter`
  - Opt-in with `ENABLE_LINKEDIN_POST_HEADLESS=true`.
  - Requires `LINKEDIN_HEADLESS_ACCESS_AUTHORIZED=true` and a non-empty
    `LINKEDIN_HEADLESS_PERMISSION_REFERENCE`.
  - Uses Playwright to read public LinkedIn post pages discovered through configured search providers or best-effort Bing.
  - When this adapter is registered, the standalone LinkedIn search and scraper adapters are suppressed as parallel publishers.

## Source Policy

Every automatic source must produce real LinkedIn post URLs and real vacancy text. The project does not log in to LinkedIn, use account cookies, proxies, fake identities, CAPTCHA bypasses, placeholder vacancies, or invented fallback records.

Every automatic LinkedIn vacancy needs a reliable publication date and must pass `LINKEDIN_POST_MAX_AGE_HOURS`, capped at 240 hours. All source vacancies pass through the common development/UI/UX/AI vacancy filter, freshness filter, localization boundary, publication limit, and SQLite deduplication before Telegram publication.

LinkedIn links can also enter through manual Telegram messages or forwards. Those messages use the normal forwarded-message parser and intake policy.

## Adding Sources

New automatic sources are out of scope unless the owner explicitly changes the source policy. If that happens, add a real `SourceAdapter`, normalize into `Vacancy`, preserve deduplication and freshness handling, document required environment variables, and add focused tests.
