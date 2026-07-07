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
  - Supports optional OpenAI/OpenAI-compatible description localization with `LOCALIZE_DESCRIPTIONS`, `OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_FALLBACK_MODELS`, and `OPENAI_BASE_URL`.

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
  - Reads labeled fields such as `Location`, `Локация`, `Stack`, `Стек`, `Salary`, `Зарплата`, and `Company`.

- `tg_vacancy_bot/linkedin_posts.py`
  - Classifies and normalizes already-available LinkedIn user-post records.
  - Requires an explicit hiring-intent phrase plus a developer/designer role.
  - Rejects candidate posts, course ads, resumes, generic hiring commentary, and records without LinkedIn URLs.
  - Produces `Vacancy` objects with `result_type="linkedin_user_post"` so the existing dedupe and publishing pipeline can be reused.

- `tg_vacancy_bot/intake.py`
  - Rejects forwarded text that does not look like an allowed development/design/AI vacancy before formatting/publishing.

- `tg_vacancy_bot/telegram_origin.py`
  - Extracts public `https://t.me/...` links from forwarded Telegram channel metadata.

- `tg_vacancy_bot/sources/`
  - Source adapter package for real job APIs and public feeds.
  - Keyed APIs are enabled only when credentials exist.
  - Parses publication dates when sources provide them and leaves `published_at=None` when they do not.
  - Includes an optional LinkedIn user-post adapter that reads only from a configured authorized JSON feed and never scrapes LinkedIn directly.

- `tg_vacancy_bot/source_polling.py`
  - Shared background source polling and publishing loop.
  - Applies the per-poll source publishing limit.
  - Publishes only source vacancies that pass the development/design/AI filter.
  - Skips publishing a vacancy when required description localization fails, so English originals do not leak into localized channel posts.
  - Filters dated source vacancies by `SOURCE_MAX_AGE_HOURS` before publishing while preserving undated vacancies for dedupe-based handling.

- `tg_vacancy_bot/storage.py`
  - SQLite deduplication by stable vacancy fingerprint.

- `tg_vacancy_bot/formatting.py`
  - Telegram HTML card formatting.

- `tg_vacancy_bot/description_localization.py`
  - Uses the real OpenAI API or an OpenAI-compatible endpoint to translate vacancy descriptions to Russian and compress long source text before normalized cards are published.
  - Raises a configuration error when localization is enabled without `OPENAI_API_KEY`.

## External Services

The bot depends on real Telegram access:

- `TELEGRAM_BOT_TOKEN` from BotFather.
- `TARGET_CHAT_ID` for the target channel/group.
- Bot admin rights in the target channel/group.
- Optional `OPERATOR_USER_IDS` to restrict who can publish through the bot.

Optional source credentials:

- `ADZUNA_APP_ID` and `ADZUNA_APP_KEY`.
- `JOOBLE_API_KEY`.
- `ENABLE_LINKEDIN_USER_POSTS=true` and `LINKEDIN_USER_POSTS_FEED_URL` for an authorized JSON feed of LinkedIn user posts.

Optional OpenAI localization:

- `LOCALIZE_DESCRIPTIONS=true`.
- `OPENAI_API_KEY` for the real OpenAI or OpenAI-compatible API.
- `OPENAI_MODEL`, defaulting to `gpt-4.1-mini`.
- `OPENAI_FALLBACK_MODELS`, optional comma-separated fallback model list. For OpenRouter, the default fallback chain is `qwen/qwen3.6-plus:free,openrouter/free`.
- `OPENAI_BASE_URL`, optional. For OpenRouter, use `https://openrouter.ai/api/v1`.

Do not replace missing external services with fake data. If a token, chat ID, API key, or permission is missing, report the missing service and stop that integration path until it is configured.

## Telegram Forwarding

For `@it_jobs_board`-style intake:

- If you forward a message to the bot in `normalize` mode, it parses the text and publishes a clean card.
- Obvious non-vacancy messages and vacancies outside the allowed development/design/AI scope are skipped.
- If the forwarded source is a public Telegram channel, the card link can point back to the original `t.me/channel/message_id`.
- If `FORWARDED_MODE=copy`, the bot applies the same allowed-vacancy intake check and then copies the original incoming message to the target chat.
- If `OPERATOR_USER_IDS` is set, unauthorized users are rejected before copy/normalize publishing.
- `/whoami` remains available so an operator can discover their Telegram user ID for `OPERATOR_USER_IDS`.

## LinkedIn Boundary

The project does not bypass LinkedIn rules or scrape LinkedIn directly. LinkedIn posts can enter the system when a user forwards text or sends a LinkedIn URL to the bot, or through `LINKEDIN_USER_POSTS_FEED_URL` when that URL points to an official API, webhook, export, or external service that is authorized to provide LinkedIn post data.
