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
  - Controls localization load with `LOCALIZATION_MAX_PER_POLL`; already-Russian descriptions bypass the model.
  - Supports optional OpenAI/OpenAI-compatible description localization with `LOCALIZE_DESCRIPTIONS`, `LOCALIZATION_PROVIDER`, `OPENAI_*`, and the built-in Groq mode (`GROQ_API_KEY`, `GROQ_MODEL`, `GROQ_FALLBACK_MODELS`).
  - Supports opt-in LinkedIn hiring-post search with `ENABLE_LINKEDIN_POST_SEARCH`, `SERPAPI_API_KEY` or `SERPER_API_KEY`, `LINKEDIN_POST_SEARCH_QUERY`, `LINKEDIN_POST_SEARCH_LOCATION`, and `LINKEDIN_POST_SEARCH_RESULTS_WANTED`.
  - Supports opt-in free LinkedIn hiring-post scraping with `ENABLE_LINKEDIN_POST_SCRAPER`, `LINKEDIN_POST_SCRAPER_QUERY`, `LINKEDIN_POST_SCRAPER_LOCATION`, `LINKEDIN_POST_SCRAPER_SEARCH_PROVIDERS`, and `LINKEDIN_POST_SCRAPER_RESULTS_WANTED`.
  - Supports opt-in JobSpy LinkedIn discovery with `ENABLE_JOBSPY_LINKEDIN`, `JOBSPY_LINKEDIN_QUERY`, `JOBSPY_LINKEDIN_LOCATION`, `JOBSPY_LINKEDIN_RESULTS_WANTED`, `JOBSPY_LINKEDIN_HOURS_OLD`, `JOBSPY_LINKEDIN_FETCH_DESCRIPTION`, and `JOBSPY_LINKEDIN_PROXIES`; keep it disabled when only ordinary LinkedIn posts are wanted.

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
  - Source adapter package for real job APIs and public feeds.
  - Keyed APIs are enabled only when credentials exist.
  - Parses publication dates when sources provide them and leaves `published_at=None` when they do not.

- `tg_vacancy_bot/source_polling.py`
  - Shared background source polling and publishing loop.
  - Applies the per-poll source publishing limit.
  - Applies the separate per-poll localization-attempt limit and stops before another localization request when that budget is exhausted.
  - Publishes only source vacancies that pass the unified vacancy filtering policy.
  - Skips publishing a vacancy when required description localization fails, so English originals do not leak into localized channel posts.
  - Filters dated source vacancies by `SOURCE_MAX_AGE_HOURS` before publishing while preserving undated vacancies for dedupe-based handling.

- `tg_vacancy_bot/storage.py`
  - SQLite deduplication by stable vacancy fingerprint.

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

The publication policy is development-first. Backend, frontend, fullstack,
mobile, GameDev, ML/LLM/AI, blockchain/Web3, UI/UX, technical PM, engineering
leadership, and explicitly coding-focused enterprise or technical-adjacent
roles may be published. Embedded/IoT is limited to software work, QA is
limited to automation/SDET, and security is limited to AppSec/DevSecOps.

DevOps/SRE/Cloud, database administration, network/sysadmin/support, manual QA,
Data Analyst/BI, ordinary product/project roles, general design, and
non-coding consulting or implementation roles are excluded.

The same policy applies to source adapters, forwarded messages, `copy` mode,
background polling, and preview commands. Role evidence must come from the
actual vacancy role or explicit technical responsibilities; a technology name
or a word such as `developer` appearing only in company or product
description is not sufficient. There are no filters by geography, work format,
salary, language, citizenship, work authorization, or employment type; valid
internships, trainee, freelance, contract, part-time, and unpaid roles remain
eligible.

## External Services

The bot depends on real Telegram access:

- `TELEGRAM_BOT_TOKEN` from BotFather.
- `TARGET_CHAT_ID` for the target channel/group.
- Bot admin rights in the target channel/group.
- Optional `OPERATOR_USER_IDS` to restrict who can publish through the bot.

Optional source credentials:

- No-key sources are controlled by `ENABLE_REMOTIVE`, `ENABLE_ARBEITNOW`, `ENABLE_REMOTEOK`, `ENABLE_HN_WHO_IS_HIRING`, `ENABLE_JOBICY`, `ENABLE_WE_WORK_REMOTELY`, `ENABLE_HIMALAYAS`, `ENABLE_REAL_WORK_FROM_ANYWHERE`, and `ENABLE_JOBSCOLLIDER`.
- LinkedIn hiring-post search is controlled by `ENABLE_LINKEDIN_POST_SEARCH=false` by default and requires `SERPAPI_API_KEY` or `SERPER_API_KEY`.
- Free LinkedIn hiring-post scraping is controlled by `ENABLE_LINKEDIN_POST_SCRAPER=false` by default and does not require an API key. `LINKEDIN_POST_SCRAPER_SEARCH_PROVIDERS` defaults to `duckduckgo,bing` so the scraper can continue through another public HTML result provider when DuckDuckGo returns an anti-bot challenge.
- JobSpy LinkedIn is controlled by `ENABLE_JOBSPY_LINKEDIN=false` by default plus `JOBSPY_LINKEDIN_*` search options. It requires the `python-jobspy` dependency but no project API key.
- `ADZUNA_APP_ID` and `ADZUNA_APP_KEY`.
- `JOOBLE_API_KEY`.

Optional OpenAI localization:

- `LOCALIZE_DESCRIPTIONS=true`.
- `LOCALIZATION_PROVIDER=openai` (default) with `OPENAI_API_KEY` for the real OpenAI or OpenAI-compatible API.
- `OPENAI_MODEL`, defaulting to `gpt-4.1-mini`.
- `OPENAI_FALLBACK_MODELS`, optional comma-separated fallback model list.
- `OPENAI_BASE_URL`, optional. For OpenRouter, use `https://openrouter.ai/api/v1`.
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

The project permits three automatic LinkedIn paths:

- `LinkedInPostSearchAdapter`, enabled only with `ENABLE_LINKEDIN_POST_SEARCH=true` and `SERPAPI_API_KEY`, searches SerpApi Google results for LinkedIn post URLs such as `linkedin.com/posts/...`, supports `||` fallback queries, and maps title/snippet/link into `Vacancy` with role-normalized titles when search titles are hashtag-heavy.
- `LinkedInPostSerperAdapter`, enabled only with `ENABLE_LINKEDIN_POST_SEARCH=true` and `SERPER_API_KEY`, searches Serper Google results for the same LinkedIn post URL scope, supports `||` fallback queries, and maps title/snippet/link into `Vacancy` with role-normalized titles when search titles are hashtag-heavy.
- `LinkedInPostScraperAdapter`, enabled only with `ENABLE_LINKEDIN_POST_SCRAPER=true`, scrapes public search-result HTML for LinkedIn post URLs such as `linkedin.com/posts/...` and maps title/snippet/link into `Vacancy` with role-normalized titles when search titles are hashtag-heavy.
- `JobSpyLinkedInAdapter`, enabled only with `ENABLE_JOBSPY_LINKEDIN=true`, calls JobSpy for LinkedIn Jobs rows and maps them into `Vacancy`.

All LinkedIn adapters are opt-in and do not use a LinkedIn account. If a provider blocks, rate-limits, lacks credentials, or returns no rows, the source path fails or returns no publishable vacancies; it must not create fake vacancies or placeholder records.
