# Architecture

## Runtime Modes

- `tg-vacancy-bot run`
  - Starts Telegram long polling.
  - Handles sent or forwarded vacancy messages.
  - Runs background public-source polling when `SOURCE_POLL_INTERVAL_SECONDS > 0`.
  - Limits source publications per cycle with `SOURCE_MAX_PUBLISH_PER_POLL`.

- `tg-vacancy-bot run-web`
  - Starts the same Telegram long polling and background public-source polling as `run`.
  - Exposes `GET /` and `GET /health` for web-hosting health checks.
  - Reads the listening port from `PORT`, defaulting to `8080`.

- `tg-vacancy-bot init-env`
  - Creates `.env` from `.env.example`.
  - Refuses to overwrite an existing `.env`.

- `tg-vacancy-bot poll-once`
  - Fetches configured public sources once.
  - Publishes new deduplicated vacancies to `TARGET_CHAT_ID`.
  - Useful for external schedulers or manual testing.

- `tg-vacancy-bot diagnose-linkedin`
  - Probes configured discovery without a browser or publishing: the SerpApi provider when `SERPAPI_API_KEY` is set, otherwise every configured free public search provider per selected intent.
  - Prints a secret-free report with safe error classes so search-engine blockages are visible.
  - Does not start Playwright, publish to Telegram, localize text, or mutate deduplication state.

- `tg-vacancy-bot process-applications-once`
  - Returns immediately when `APPLICATION_QUEUE_ENABLED=false`.
  - Uses Telegram `getUpdates` to drain queued application callbacks and private queue-resume messages in batches.
  - Requires one allowlisted operator and a queue profile configured through private environment variables.
  - Persists only the latest `/queue_resume` document `file_id` and safe filename in SQLite; the document bytes remain in Telegram.
  - Downloads the selected resume by Telegram `file_id` into a temporary directory.
  - Runs the allowlisted browser adapter, persists the factual application status in SQLite, sends a private result, and exits.
  - Never retries a callback that reached `submitting`, because the external form may already have accepted it.

- `tg-vacancy-bot check-telegram`
  - Calls the real Telegram API.
  - Validates the bot token, target chat visibility, and bot membership/posting status.
  - Reports whether the operator allowlist is enabled without printing user IDs.
  - Does not print the bot token.

- `tg-vacancy-bot preview-message`
  - Parses local message text from stdin or `--file`.
  - Prints the Telegram card HTML without publishing anything.
  - Useful for checking forwarded-message parser quality before enabling live posting.

- `tg-vacancy-bot publish-message`
  - Parses one local UTF-8 message file.
  - Publishes the normalized vacancy to the real `TARGET_CHAT_ID`.
  - Uses the same deduplication store as source polling.

## Modules

- `tg_vacancy_bot/config.py`
  - Loads private runtime configuration from `.env`.
  - Requires `TELEGRAM_BOT_TOKEN` and `TARGET_CHAT_ID` for real publishing.
  - Supports optional `OPERATOR_USER_IDS` for publish access control.
  - Controls source polling with `SOURCE_POLL_INTERVAL_SECONDS`, `SOURCE_MAX_PUBLISH_PER_POLL`, and `SOURCE_MAX_AGE_HOURS`.
  - Supports localization for manual messages and requires it for every source vacancy before publication.
  - Supports optional OpenAI/OpenAI-compatible description localization with `LOCALIZE_DESCRIPTIONS`, `LOCALIZATION_PROVIDER`, `OPENAI_*`, and the built-in Groq mode (`GROQ_API_KEY`, `GROQ_MODEL`, `GROQ_FALLBACK_MODELS`).
  - Supports opt-in, globally scoped LinkedIn hiring-post search with `ENABLE_LINKEDIN_POST_SEARCH`, `SERPAPI_API_KEY`, `LINKEDIN_POST_SEARCH_QUERY`, and `LINKEDIN_POST_SEARCH_RESULTS_WANTED`.
  - Supports opt-in, globally scoped free LinkedIn hiring-post scraping with `ENABLE_LINKEDIN_POST_SCRAPER`, `LINKEDIN_POST_SCRAPER_QUERY`, `LINKEDIN_POST_SCRAPER_SEARCH_PROVIDERS`, and `LINKEDIN_POST_SCRAPER_RESULTS_WANTED`.
  - Supports opt-in Apify-backed LinkedIn post-body search with `ENABLE_LINKEDIN_POST_APIFY`, `APIFY_API_TOKEN`, `LINKEDIN_POST_APIFY_ACTOR`, `LINKEDIN_POST_APIFY_SEARCH_QUERIES`, `LINKEDIN_POST_APIFY_POSTED_LIMIT`, `LINKEDIN_POST_APIFY_MAX_POSTS`, and `LINKEDIN_POST_APIFY_TIMEOUT_SECONDS`.
   - Supports opt-in, globally scoped headless parsing of publicly available LinkedIn posts with `ENABLE_LINKEDIN_POST_HEADLESS`, `LINKEDIN_HEADLESS_ACCESS_AUTHORIZED`, `LINKEDIN_HEADLESS_PERMISSION_REFERENCE`, `LINKEDIN_POST_HEADLESS_QUERY`, `LINKEDIN_POST_HEADLESS_RESULTS_WANTED`, `LINKEDIN_POST_SEARCH_INTENTS_PER_CYCLE`, and `LINKEDIN_POST_HEADLESS_TIMEOUT_SECONDS`. A blank query activates the built-in Russian/English intents across the two allowed role families (frontend and fullstack), phrased for junior or entry-level candidates. SerpApi requests use Google’s closest supported recency window before raw URL candidates reach the exact freshness decision. Direct page reading remains disabled unless both the authorization flag and a documented permission reference are present. Every automatic LinkedIn adapter requires a reliable publication date before publication and enforces `LINKEDIN_POST_MAX_AGE_HOURS` with a hard maximum of 240 hours / 10 days.

- `tg_vacancy_bot/access_control.py`
  - Parses operator allowlists and checks whether a sender may publish through the bot.

- `tg_vacancy_bot/env_setup.py`
  - Safe `.env` bootstrap helper.

- `tg_vacancy_bot/console.py`
  - Writes Unicode CLI output safely on Windows consoles.

- `tg_vacancy_bot/telegram_check.py`
  - Real Telegram API diagnostics for setup verification.

- `tg_vacancy_bot/preview.py`
  - Local parser/formatter preview for forwarded messages.

- `tg_vacancy_bot/bot.py`
  - Telegram message handlers.
  - Supports `FORWARDED_MODE=normalize` and `FORWARDED_MODE=copy`.
  - Provides `/help`, `/whoami`, and `/status` operator commands.

- `tg_vacancy_bot/deployment.py`
  - Hosts the minimal HTTP health endpoint used by web-service deployments.

- `tg_vacancy_bot/application_queue.py`
  - Implements the one-shot Telegram callback consumer used by GitHub Actions.
  - Keeps profile secrets out of SQLite and keeps resume bytes out of Actions cache.
  - Preserves update ordering and confirms Telegram offsets only after processing a batch.
  - Runs the bot process alongside the health endpoint without changing Telegram publishing behavior.

- `tg_vacancy_bot/parser.py`
  - Extracts URL, title, stack, location, salary, and source from free-form vacancy text.
  - Reads labeled fields such as `Location`, `Stack`, `Salary`, and `Company`.
  - Marks manually supplied LinkedIn URLs as source `LinkedIn`.

- `tg_vacancy_bot/intake.py`
  - Rejects forwarded text that does not match the unified vacancy filtering policy before formatting/publishing.

- `tg_vacancy_bot/telegram_origin.py`
  - Extracts public `https://t.me/...` links from forwarded Telegram channel metadata.

- `tg_vacancy_bot/sources/`
  - Source adapter package for LinkedIn hiring-post discovery only.
  - Registers keyed search, free search-result scraping, or permission-gated headless LinkedIn post parsing according to the configured opt-in flags.
  - Every automatic LinkedIn vacancy needs a reliable publication date before it can reach source polling.

- `tg_vacancy_bot/source_polling.py`
  - Shared background source polling and publishing loop.
  - Applies the per-poll source publishing limit.
  - Publishes only source vacancies that pass the unified vacancy filtering policy.
  - Always runs source descriptions through the localization boundary before publication; if the provider fails, logs the error and publishes the original description rather than losing the vacancy.
  - Filters dated source vacancies by `SOURCE_MAX_AGE_HOURS` before publishing while preserving undated vacancies for dedupe-based handling.

- `tg_vacancy_bot/storage.py`
  - SQLite deduplication by stable vacancy fingerprint.
  - URL-based fingerprints are canonicalized first (`models.canonical_identity_url`): scheme/host lowercased, fragment dropped, tracking parameters (utm_*, fbclid, gclid, and similar) removed, trailing path slash stripped — so the same vacancy arriving from different sources with URL variants deduplicates once.

- `tg_vacancy_bot/formatting.py`
  - Telegram HTML card formatting.

- `tg_vacancy_bot/description_localization.py`
  - Uses the real OpenAI API or an OpenAI-compatible endpoint to translate vacancy descriptions to Russian and compress long source text before normalized cards are published.
  - Rejects empty localization responses and non-Russian/original-language responses, then tries the next configured fallback model before publishing.
  - Raises a configuration error when localization is enabled without the key required by the selected provider.

## Vacancy Filtering Policy

The full, maintained category matrix and implementation plan live in
[`docs/vacancy-filtering-policy-plan.md`](vacancy-filtering-policy-plan.md).
Update that document first when the channel's vacancy policy changes, then
reflect the stabilized behavior here.

The publication policy is narrow by design. A post may be published only when
it really seeks Junior-level Frontend or Fullstack developers. The unified
check in `tg_vacancy_bot/sources/filters.py` requires all of:

- a hiring signal (`hiring`, `looking for`, `join our team`, `open role`,
  `ищем`, `нанимаем`, `вакансия`, ...);
- explicit frontend or fullstack role evidence (`frontend`, `front-end`,
  `фронтенд`, `fullstack`, `full-stack`, `фулстек`, ...);
- junior or entry-level evidence (`junior`, `intern`, `trainee`, `стажер`,
  `entry-level`, `без опыта`, ...).

Posts are rejected when a non-junior seniority level (`senior`, `middle`,
`lead`, ...) is attached directly to a frontend/fullstack role, when the text
advertises courses, bootcamps, or mentorship instead of a job, or when any of
the required signals above is missing. Every decision carries a diagnostic
reason that is covered by tests.

The same policy applies to source adapters, forwarded messages, `copy` mode,
background polling, and preview commands. Role evidence must come from the
actual vacancy role; there are no filters by geography, work format, salary,
language, citizenship, work authorization, or employment type.

## External Services

The bot depends on real Telegram access:

- `TELEGRAM_BOT_TOKEN` from BotFather.
- `TARGET_CHAT_ID` for the target channel/group.
- Bot admin rights in the target channel/group.
- Optional `OPERATOR_USER_IDS` to restrict who can publish through the bot.

Optional source credentials:

- LinkedIn hiring-post search is controlled by `ENABLE_LINKEDIN_POST_SEARCH=false` by default and requires `SERPAPI_API_KEY`. Keyed search requests retry transient failures (HTTP 429, 5xx, network errors) with a bounded exponential backoff of two retries (2s, 4s); other client errors fail immediately, and the final failure still reports only the safe status class.
- Free LinkedIn hiring-post scraping is controlled by `ENABLE_LINKEDIN_POST_SCRAPER=false` by default and does not require an API key. `LINKEDIN_POST_SCRAPER_SEARCH_PROVIDERS` defaults to `bing_rss,duckduckgo,bing,duckduckgo_lite,mojeek` so the scraper first consumes Bing's RSS output, then falls back to public HTML result providers when RSS returns no usable LinkedIn posts. HTML providers that return anti-bot challenges are skipped; a failing provider is isolated so the remaining providers still run. The scraper does not bypass CAPTCHA or protection pages.
- Apify LinkedIn post-body search is controlled by `ENABLE_LINKEDIN_POST_APIFY=false` by default and requires `APIFY_API_TOKEN`. The default Actor is `harvestapi/linkedin-post-search`; it accepts `||`-separated queries no longer than 85 characters, uses a 24-hour Actor-side window, and reads the returned `content`, URL, author, and date. The adapter rejects entries without a reliable date or without both a hiring intent and a supported development role before the common filters run. Apify is an independent hosted provider, not an official LinkedIn API, and may incur usage charges.
- Headless LinkedIn post parsing is controlled by `ENABLE_LINKEDIN_POST_HEADLESS=false` by default. It uses Playwright and does not use a LinkedIn account, proxy, or protection bypass. Direct reading additionally requires `LINKEDIN_HEADLESS_ACCESS_AUTHORIZED=true` and a non-empty `LINKEDIN_HEADLESS_PERMISSION_REFERENCE` that records documented LinkedIn permission or an approved access path. Without that gate the adapter is not registered. It uses `SERPAPI_API_KEY` for keyed link discovery when present; without a key it discovers links through its own free public search pipeline (Bing RSS, DuckDuckGo HTML, Bing HTML, DuckDuckGo Lite, Mojeek, paginated Bing HTML). Guest-page reads are paced with jittered delays, run with a consistent real-Chrome user agent and the browser automation flag disabled, wait briefly for late-rendering text, retry an HTTP 429/999 answer once after backoff, and retry a canonical `/posts/...` login redirect once through the public `/feed/update/urn:li:activity:...` form before skipping.

Optional OpenAI localization:

- `LOCALIZE_DESCRIPTIONS=true`.
- `LOCALIZATION_PROVIDER=openai` (default) with `OPENAI_API_KEY` for the real OpenAI or OpenAI-compatible API.
- `OPENAI_MODEL`, defaulting to `gpt-4.1-mini`. For the currently tested free OpenRouter path, use `nvidia/nemotron-3-super-120b-a12b:free`.
- `OPENAI_FALLBACK_MODELS`, optional comma-separated fallback model list.
- `OPENAI_BASE_URL`, optional. For OpenRouter, use `https://openrouter.ai/api/v1`.
- When `OPENAI_BASE_URL` points to OpenRouter and no fallback list is configured, the bot tries `nvidia/nemotron-3-super-120b-a12b:free`, `openai/gpt-oss-20b:free`, and `openrouter/free`, then appends the paid `openai/gpt-4.1-mini` fallback.
- `LOCALIZATION_PROVIDER=groq` with `GROQ_API_KEY` uses Groq's OpenAI-compatible API at `https://api.groq.com/openai/v1`.
- Groq defaults to `llama-3.1-8b-instant` with `openai/gpt-oss-20b` as a fallback. `GROQ_MODEL` and `GROQ_FALLBACK_MODELS` allow model replacement without a code change.

Do not replace missing external services with fake data. If a token, chat ID, API key, or permission is missing, report the missing service and stop that integration path until it is configured.

## Telegram Forwarding

For `@it_jobs_board`-style intake:

- If you forward a message to the bot in `normalize` mode, it parses the text and publishes a clean card.
- Obvious non-vacancy messages and vacancies outside the unified vacancy filtering policy are skipped.
- If the forwarded source is a public Telegram channel, the card link can point back to the original `t.me/channel/message_id`.
- If `FORWARDED_MODE=copy`, the bot applies the same allowed-vacancy intake check and then copies the original incoming message to the target chat.
- If `OPERATOR_USER_IDS` is set, unauthorized users are rejected before copy/normalize publishing.
- `/whoami` remains available so an operator can discover their Telegram user ID for `OPERATOR_USER_IDS`.

## LinkedIn Boundary

The project permits four automatic LinkedIn adapters across four opt-in paths:

- `LinkedInPostSearchAdapter`, enabled only with `ENABLE_LINKEDIN_POST_SEARCH=true` and `SERPAPI_API_KEY`, searches SerpApi Google results for LinkedIn post URLs such as `linkedin.com/posts/...`, supports `||` fallback queries, and maps title/snippet/link into `Vacancy` with role-normalized titles when search titles are hashtag-heavy.
- `LinkedInPostScraperAdapter`, enabled only with `ENABLE_LINKEDIN_POST_SCRAPER=true`, scrapes public search-result HTML (Bing RSS, DuckDuckGo HTML, Bing HTML, DuckDuckGo Lite, Mojeek) for LinkedIn post URLs such as `linkedin.com/posts/...` and maps title/snippet/link into `Vacancy` with role-normalized titles when search titles are hashtag-heavy.
- `LinkedInPostApifyAdapter`, enabled only with `ENABLE_LINKEDIN_POST_APIFY=true` and `APIFY_API_TOKEN`, runs the configured Apify Actor, maps full post-body results into `Vacancy`, and applies deterministic hiring-intent/role matching before common filtering and SQLite deduplication.
- `LinkedInPostHeadlessAdapter`, enabled only when the headless flag and documented permission gate are both satisfied, discovers public LinkedIn post links through configured SerpApi search when a key exists, then best-effort lightweight HTTP providers (Bing RSS, DuckDuckGo HTML, Bing HTML, DuckDuckGo Lite, Mojeek, paginated Bing HTML), and finally reads Bing result pages inside the same clean browser context when HTTP discovery produced no candidates. The browser maps page text into `Vacancy` only when the final URL remains on a supported LinkedIn post path and no login or protection page is detected; guest reads are paced with jitter, retry 429/999 once after a backoff, retry a login-walled `/posts/` URL once through its public feed-update form, and fall back to the real public search result that discovered the link (title, snippet, activity-ID date) when direct reading stays blocked. While this pipeline is registered, standalone search/scraper adapters are not registered as parallel LinkedIn publishers.

All LinkedIn adapters are opt-in and do not use a LinkedIn account. If a provider blocks, rate-limits, lacks credentials, or returns no rows, the source path fails or returns no publishable vacancies; it must not create fake vacancies or placeholder records. Every published headless vacancy is backed by a real public source: the post page itself or the public search result that indexed it.
