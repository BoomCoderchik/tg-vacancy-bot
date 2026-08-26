# Sources

## Active Sources

Automatic polling is limited to LinkedIn hiring posts.

- `LinkedInPostSearchAdapter`
  - Opt-in with `ENABLE_LINKEDIN_POST_SEARCH=true`.
  - Uses SerpApi when `SERPAPI_API_KEY` is set.
  - Reads only publicly indexed `linkedin.com/posts/...` and `linkedin.com/feed/update/...` results.

- `LinkedInPostScraperAdapter`
  - Opt-in with `ENABLE_LINKEDIN_POST_SCRAPER=true`.
  - Uses public search-result providers such as Bing RSS, DuckDuckGo HTML, Bing HTML, DuckDuckGo Lite, and Mojeek.
  - Skips CAPTCHA, anti-bot, empty, or malformed provider responses instead of bypassing protection; one failing provider never blocks the remaining providers.

- `LinkedInPostHeadlessAdapter`
  - Opt-in with `ENABLE_LINKEDIN_POST_HEADLESS=true`.
  - Requires `LINKEDIN_HEADLESS_ACCESS_AUTHORIZED=true` and a non-empty
    `LINKEDIN_HEADLESS_PERMISSION_REFERENCE`.
  - Uses Playwright to read public LinkedIn post pages discovered through an optional keyed provider or, without a key, through lightweight public search requests: Bing RSS, DuckDuckGo HTML, Bing HTML, DuckDuckGo Lite, Mojeek, then paginated Bing HTML (`LINKEDIN_HEADLESS_DISCOVERY_PAGES`, default 3). When HTTP discovery produced no candidates, Bing result pages are read inside the same clean browser context. Protection screens and unexpected redirect domains end that engine's attempt instead of being bypassed.
  - Guest-page reading is paced with jittered delays, uses a consistent real-Chrome user agent with the automation flag disabled, waits briefly for late-rendering text, retries an HTTP 429/999 answer once after a backoff, and retries a canonical `/posts/...` login redirect once through the public `/feed/update/urn:li:activity:...` form before skipping.
  - When direct reading stays blocked by a login wall, publishes the vacancy from the real public search result that discovered the link (title, snippet, activity-ID date) instead of dropping it; protection pages and off-domain redirects are never bypassed.
  - The built-in search profile covers frontend and fullstack in junior/entry-level and internship/trainee variants in Russian and English.
  - When this adapter is registered, the standalone LinkedIn search and scraper adapters are suppressed as parallel publishers.

- `LinkedInPostApifyAdapter`
  - Opt-in with `ENABLE_LINKEDIN_POST_APIFY=true` and `APIFY_API_TOKEN`.
  - Runs the configured Apify Actor (by default `harvestapi/linkedin-post-search`) with keyword queries.
  - Reads the structured post body, direct LinkedIn post URL, author, and publication date.
  - Keeps only posts whose body contains both a hiring signal and a supported development role.

## Source Policy

Every automatic source must produce real LinkedIn post URLs and real vacancy text. The bot does not log in to LinkedIn, store account cookies, create fake identities, perform CAPTCHA bypasses, publish placeholder vacancies, or invent fallback records. Every published headless vacancy is backed by a real public source: the post page itself or the public search result that indexed it. The Apify adapter is an explicitly enabled external hosted source; it sends only configured search input and reads the Actor's structured output. The selected Actor is independent from LinkedIn, so review its current terms, pricing, and behavior before enabling it.

Every automatic LinkedIn vacancy needs a reliable publication date and must pass `LINKEDIN_POST_MAX_AGE_HOURS`, capped at 240 hours. All source vacancies pass through the common Junior Frontend/Fullstack vacancy filter, freshness filter, localization boundary, publication limit, and SQLite deduplication before Telegram publication.

LinkedIn links can also enter through manual Telegram messages or forwards. Those messages use the normal forwarded-message parser and intake policy.

## Adding Sources

New automatic sources are out of scope unless the owner explicitly changes the source policy. If that happens, add a real `SourceAdapter`, normalize into `Vacancy`, preserve deduplication and freshness handling, document required environment variables, and add focused tests.
