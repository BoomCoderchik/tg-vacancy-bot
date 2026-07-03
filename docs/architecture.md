# Architecture

## Runtime Modes

- `tg-vacancy-bot run`
  - Starts Telegram long polling.
  - Handles sent or forwarded vacancy messages.
  - Runs background public-source polling when `SOURCE_POLL_INTERVAL_SECONDS > 0`.

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
  - Does not print the bot token.

- `tg-vacancy-bot preview-message`
  - Parses local message text from stdin or `--file`.
  - Prints the Telegram card HTML without publishing anything.
  - Useful for checking forwarded-message parser quality before enabling live posting.

## Modules

- `tg_vacancy_bot/config.py`
  - Loads private runtime configuration from `.env`.
  - Requires `TELEGRAM_BOT_TOKEN` and `TARGET_CHAT_ID` for real publishing.
  - Supports optional `OPERATOR_USER_IDS` for publish access control.

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

- `tg_vacancy_bot/parser.py`
  - Extracts URL, title, stack, location, salary, and source from free-form vacancy text.
  - Reads labeled fields such as `Location`, `Локация`, `Stack`, `Стек`, `Salary`, `Зарплата`, and `Company`.

- `tg_vacancy_bot/intake.py`
  - Rejects forwarded text that does not look like an IT vacancy before formatting/publishing.

- `tg_vacancy_bot/telegram_origin.py`
  - Extracts public `https://t.me/...` links from forwarded Telegram channel metadata.

- `tg_vacancy_bot/sources/`
  - Source adapter package for real job APIs and public feeds.
  - Keyed APIs are enabled only when credentials exist.

- `tg_vacancy_bot/source_polling.py`
  - Shared background source polling and publishing loop.

- `tg_vacancy_bot/storage.py`
  - SQLite deduplication by stable vacancy fingerprint.

- `tg_vacancy_bot/formatting.py`
  - Telegram HTML card formatting.

## External Services

The bot depends on real Telegram access:

- `TELEGRAM_BOT_TOKEN` from BotFather.
- `TARGET_CHAT_ID` for the target channel/group.
- Bot admin rights in the target channel/group.
- Optional `OPERATOR_USER_IDS` to restrict who can publish through the bot.

Optional source credentials:

- `ADZUNA_APP_ID` and `ADZUNA_APP_KEY`.
- `JOOBLE_API_KEY`.

Do not replace missing external services with fake data. If a token, chat ID, API key, or permission is missing, report the missing service and stop that integration path until it is configured.

## Telegram Forwarding

For `@it_jobs_board`-style intake:

- If you forward a message to the bot in `normalize` mode, it parses the text and publishes a clean card.
- In `normalize` mode, obvious non-vacancy messages are skipped.
- If the forwarded source is a public Telegram channel, the card link can point back to the original `t.me/channel/message_id`.
- If `FORWARDED_MODE=copy`, the bot copies the original incoming message to the target chat.
- If `OPERATOR_USER_IDS` is set, unauthorized users are rejected before copy/normalize publishing.
- `/whoami` remains available so an operator can discover their Telegram user ID for `OPERATOR_USER_IDS`.

## LinkedIn Boundary

The project does not bypass LinkedIn rules or scrape LinkedIn directly. LinkedIn posts can enter the system when a user forwards text or sends a LinkedIn URL to the bot.
