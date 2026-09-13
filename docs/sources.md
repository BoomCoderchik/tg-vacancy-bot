# Sources

## Active Sources

Automatic polling covers LinkedIn hiring posts and Russia-wide open-web
vacancies that follow the operator's `/filters` selection.

### LinkedIn sources

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

- `LinkedInJobsGuestAdapter`
  - Off by default for the bot-target pipeline; opt-in with `ENABLE_LINKEDIN_JOBS_GUEST=true`.
  - Reads LinkedIn's own public, logged-out job listings through the guest search endpoint and public job pages; no account, key, or protection bypass is involved.
  - Searches each configured keyword (`LINKEDIN_JOBS_GUEST_KEYWORDS`) within the freshness window, keeps only listings whose title carries junior-level and frontend/fullstack evidence, then reads the public job page for the real posting text.
  - Works from any IP that can reach LinkedIn directly, including datacenter runners where search engines block scraping.

### Russia-wide sources

- `RussiaVacancySearchAdapter`
  - Opt-in with `ENABLE_RUSSIA_SEARCH=true`.
  - Searches the whole open web through the same free public search providers as the LinkedIn scraper (Bing RSS, DuckDuckGo HTML, Bing HTML, DuckDuckGo Lite, Mojeek; optional SerpApi is not used here). No `site:` restriction: Russian job domains (hh.ru, career.habr.com, superjob.ru, getmatch.ru, vc.ru, and others from `RU_JOB_DOMAIN_HINTS`) are only a result-ordering preference, never a domain filter.
  - Queries are built from the active `/filters` selection (specialties × grades, Russian and English) when `RUSSIA_SEARCH_QUERY` is empty; a manual `||`-separated query always wins.
  - Keeps only real `http(s)` pages, skips search-engine and LinkedIn domains, drops results without a title or snippet, maps dates through absolute and Russian/English relative date parsing, and passes undated results to the base layer.
  - Skips anti-bot challenge pages instead of bypassing them; one failing provider never blocks the remaining providers.

- `TelegramVacancyChannelAdapter`
  - Opt-in with `ENABLE_RUSSIA_TELEGRAM=true` and a comma-separated `RUSSIA_TELEGRAM_CHANNELS` list of public channel usernames (no `@` needed).
  - Reads only public channels through their public `https://t.me/s/<username>` preview page. No Telegram API token, account login, CAPTCHA handling, or protection bypass is involved; private or blocked channels are skipped, not bypassed.
  - Maps each public post into a `Vacancy` with its post link, text, and best-effort publication date (from the post's ISO `time` attribute or a text fallback), capped per channel by `RUSSIA_TELEGRAM_MAX_POSTS_PER_CHANNEL`.
  - Undated posts pass to the base layer; dated posts are filtered by the polling freshness window.

## Source Policy

Every automatic source must produce real vacancy pages, post URLs, and real vacancy text. The bot does not log in to services, store account cookies, create fake identities, perform CAPTCHA bypasses, publish placeholder vacancies, or invent fallback records. LinkedIn hiring posts additionally require a reliable publication date and pass `LINKEDIN_POST_MAX_AGE_HOURS`, capped at 240 hours. All source vacancies pass through the common vacancy filter (the active `/filters` specialties and grades), freshness filter, localization boundary, publication limit, and SQLite deduplication before Telegram publication. The Russia-wide sources deliberately follow the base-layer freshness behavior: dated results older than `SOURCE_MAX_AGE_HOURS` are dropped, while undated results rely on source ordering, the per-poll publication limit, and SQLite deduplication.

LinkedIn links can also enter through manual Telegram messages or forwards. Those messages use the normal forwarded-message parser and intake policy.

## Adding Sources

New automatic sources follow the project source-adapter contract: add a real `SourceAdapter`, normalize into `Vacancy`, preserve deduplication and freshness handling, document required environment variables, and add focused tests. The owner authorizes the linkedin, Russia internet-search, and public Telegram-channel source families; other automatic sources still need an explicit source-policy change.
