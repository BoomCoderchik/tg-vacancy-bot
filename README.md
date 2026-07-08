# TG Vacancy Bot

Telegram bot for collecting IT vacancies from forwarded messages and public job sources, then publishing them to a target Telegram channel in a compact card format.

## What Works Now

- Accepts messages forwarded or sent to the bot.
- Publishes to a configured Telegram channel/group.
- Supports two forwarded-message modes:
  - `normalize`: parse text and publish a clean vacancy card.
  - `copy`: copy the original message to the target channel after the same allowed-vacancy intake check.
- Publishes only development/design/AI vacancies: backend, frontend, fullstack, design, LLM, AI, and clear software developer/engineer roles.
- Stores message fingerprints in SQLite to avoid duplicates.
- Includes source adapters for Remotive, Arbeitnow, RemoteOK, Hacker News "Who is Hiring", Jobicy, We Work Remotely, Himalayas, Real Work From Anywhere, JobsCollider, Adzuna, Jooble, opt-in LinkedIn hiring-post search, and opt-in JobSpy LinkedIn Jobs discovery.
- Polls configured public sources in the background while the bot is running.

## Near-Real-Time Parser Mode

For an always-on vacancy parser, run the bot continuously with source polling enabled:

```dotenv
SOURCE_POLL_INTERVAL_SECONDS=60
SOURCE_MAX_AGE_HOURS=48
SOURCE_MAX_PUBLISH_PER_POLL=20
```

The bot does not wait for manual forwarding in this mode. It polls real configured sources, publishes vacancies that are new to the bot, skips repeats through SQLite deduplication, and drops dated source vacancies older than `SOURCE_MAX_AGE_HOURS`. Vacancies from sources without a publication date are not assigned a fake date; they rely on source ordering, the publish limit, and deduplication.

Sixty-second polling is near-real-time for ordinary job APIs. Truly instant publishing requires a source-provided webhook or stream.

## LinkedIn Hiring Post Discovery

To find ordinary LinkedIn posts like "Ищем Junior Front-End Developer..." rather than LinkedIn Jobs cards, enable the [SerpApi](https://serpapi.com/search-api)-backed post search source:

```dotenv
ENABLE_LINKEDIN_POST_SEARCH=true
SERPAPI_API_KEY=
LINKEDIN_POST_SEARCH_QUERY=(site:linkedin.com/posts OR site:linkedin.com/feed/update) ("ищем" OR "ищет" OR "в команду" OR "we are hiring" OR "we're hiring" OR hiring) (frontend OR "front-end" OR backend OR fullstack OR "full-stack" OR designer OR "AI engineer" OR "ML engineer" OR "LLM engineer" OR разработчик OR инженер)
LINKEDIN_POST_SEARCH_LOCATION=Kazakhstan
LINKEDIN_POST_SEARCH_RESULTS_WANTED=10
```

This source uses SerpApi Google Search results for publicly indexed LinkedIn post URLs. It publishes only real search results with a short snippet-based summary and the LinkedIn post link. If `SERPAPI_API_KEY` is missing, the source is not registered.

## JobSpy LinkedIn Jobs Discovery

LinkedIn Jobs discovery is available as an explicit opt-in source through [JobSpy](https://github.com/speedyapply/JobSpy). It is intended to send new LinkedIn Jobs links in the configured development/design/AI search scope through the same source polling flow as the other adapters: intake filter, freshness filter, SQLite deduplication, publication limit, and Telegram publishing.

Enable it only when you accept LinkedIn's operational risk around automated access:

```dotenv
ENABLE_JOBSPY_LINKEDIN=true
JOBSPY_LINKEDIN_QUERY=backend OR frontend OR fullstack OR designer OR "AI engineer" OR "ML engineer" OR "LLM engineer"
JOBSPY_LINKEDIN_LOCATION=Worldwide
JOBSPY_LINKEDIN_RESULTS_WANTED=20
JOBSPY_LINKEDIN_HOURS_OLD=48
JOBSPY_LINKEDIN_FETCH_DESCRIPTION=false
JOBSPY_LINKEDIN_PROXIES=
```

By default this publishes lightweight link cards from JobSpy LinkedIn Jobs search results. Set `JOBSPY_LINKEDIN_FETCH_DESCRIPTION=true` only if you want JobSpy to request each LinkedIn job page for fuller descriptions; that mode is slower and more likely to be rate-limited. No LinkedIn account login or browser automation is used.

## Required Telegram Setup

1. Create a bot in [@BotFather](https://t.me/BotFather).
2. Copy the bot token into `.env` as `TELEGRAM_BOT_TOKEN`.
3. Create your target channel or group.
4. Add the bot as an admin to that target channel/group.
5. Put the target chat into `.env` as `TARGET_CHAT_ID`.
6. For production safety, put your Telegram user ID into `OPERATOR_USER_IDS`.

For a public channel, `TARGET_CHAT_ID` can be `@channel_username`. For a private channel/group, use the numeric chat ID.

`OPERATOR_USER_IDS` is optional during first setup. When it is set, only listed Telegram users can publish forwarded messages, copy messages, or view `/status`. Use a comma-separated list, for example `OPERATOR_USER_IDS=123456789,987654321`.

To find your Telegram user ID, run the bot without `OPERATOR_USER_IDS` first, send `/whoami` to the bot, copy the returned ID into `.env`, then restart the bot.

## Local Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
tg-vacancy-bot init-env
```

Fill in `.env`, then run:

```powershell
tg-vacancy-bot run
```

Before running the bot continuously, validate the real Telegram integration:

```powershell
tg-vacancy-bot check-telegram
```

To poll public sources once and publish new vacancies:

```powershell
tg-vacancy-bot poll-once
```

When `SOURCE_POLL_INTERVAL_SECONDS` is greater than `0`, `tg-vacancy-bot run` also polls configured public sources in the background while it listens for forwarded messages.
`SOURCE_MAX_PUBLISH_PER_POLL` limits how many source vacancies can be published in one polling cycle, which prevents first-run flooding.

For web-hosting deployment, use:

```powershell
tg-vacancy-bot run-web
```

This runs the same Telegram bot and source polling loop with `GET /` and `GET /health` endpoints for platforms that require an open port. For reliable always-on parsing, prefer the VM path in `docs/deployment.md`.

## Description Localization

To translate vacancy descriptions into Russian and compress long source text before publishing, set:

```dotenv
LOCALIZE_DESCRIPTIONS=true
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4.1-mini
OPENAI_FALLBACK_MODELS=
OPENAI_BASE_URL=
```

This uses the real OpenAI API, or an OpenAI-compatible endpoint such as OpenRouter, for normalized cards from forwarded messages, `publish-message`, and public source polling. If localization is enabled without `OPENAI_API_KEY`, publishing stops with a clear configuration error instead of using fake or placeholder text.

## Preview And Manual Publish

To preview how a forwarded vacancy will be normalized before posting:

```powershell
Get-Content .\sample-message.txt -Raw | tg-vacancy-bot preview-message
```

Or:

```powershell
tg-vacancy-bot preview-message --file .\sample-message.txt
```

To publish that same normalized card to the real target chat after `.env` is configured:

```powershell
tg-vacancy-bot publish-message --file .\sample-message.txt
```

## Forwarded Message Flow

Send or forward a vacancy message to the bot. In `normalize` mode, the bot parses the text into a compact vacancy card and publishes it to the target chat. In `copy` mode, the bot copies the original message to the target channel.

Messages that do not look like allowed development/design/AI vacancies are skipped before publishing. In `copy` mode, the bot still applies this intake check, then copies the original accepted message as-is.

## Bot Commands

- `/start` or `/help`: shows the forwarding instructions.
- `/whoami`: returns your Telegram user ID for `OPERATOR_USER_IDS`.
- `/status`: shows the active forwarding mode, target chat, polling interval, and enabled sources without exposing secrets.

## LinkedIn Boundary

This project now permits two documented, opt-in LinkedIn paths: SerpApi-backed public hiring-post search and JobSpy-backed LinkedIn Jobs discovery. It does not log in with a LinkedIn account, automate a browser, invent vacancies, or publish fake fallback records when LinkedIn blocks or returns no results.

LinkedIn links can also enter when an operator manually sends or forwards vacancy text containing a LinkedIn URL to the Telegram bot. In that case the normal forwarded-message parser can keep the URL and mark the vacancy source as `LinkedIn`.
