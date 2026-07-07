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
- Includes source adapters for Remotive, Arbeitnow, RemoteOK, Hacker News "Who is Hiring", Jobicy, We Work Remotely, Himalayas, Real Work From Anywhere, and JobsCollider.
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

For free web-hosting deployment, use:

```powershell
tg-vacancy-bot run-web
```

This runs the same Telegram bot and source polling loop with a small HTTP health endpoint for platforms that require an open port. For reliable free always-on parsing, prefer the VM path in `docs/deployment.md`.

To translate vacancy descriptions into Russian and compress long source text before publishing, set:

```dotenv
LOCALIZE_DESCRIPTIONS=true
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4.1-mini
OPENAI_FALLBACK_MODELS=
OPENAI_BASE_URL=
```

This uses the real OpenAI API, or an OpenAI-compatible endpoint such as OpenRouter, for normalized cards from forwarded messages, `publish-message`, and public source polling. For OpenRouter, use `OPENAI_BASE_URL=https://openrouter.ai/api/v1` and set `OPENAI_MODEL` to an OpenRouter model slug such as `qwen/qwen3.6-plus:free`. When OpenRouter is configured and `OPENAI_FALLBACK_MODELS` is empty, the bot automatically retries empty or failed localization responses with `qwen/qwen3.6-plus:free` and `openrouter/free`. You can override that chain with a comma-separated `OPENAI_FALLBACK_MODELS` value. If localization is enabled without `OPENAI_API_KEY`, publishing stops with a clear configuration error instead of using fake or placeholder text.

The scheduled GitHub Actions source poll requires localization to be available before it posts to Telegram. If `OPENAI_API_KEY` is missing or the formatter regresses to the old card style, the workflow fails before publishing.

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

Send or forward a vacancy message to the bot. In `normalize` mode, the bot will publish a card like:

```text
💼 Senior Full-Stack Engineer

📍 Локация: Удаленно

🧠 Стек: Python, FastAPI, React, AWS

Описание
...

🔗 Смотреть вакансию
▫️ Источник: Telegram
```

In `copy` mode, the bot copies the original message to the target channel.

Messages that do not look like allowed development/design/AI vacancies are skipped before publishing. In `copy` mode, the bot still applies this intake check, then copies the original accepted message as-is.

## Bot Commands

- `/start` or `/help`: shows the forwarding instructions.
- `/whoami`: returns your Telegram user ID for `OPERATOR_USER_IDS`.
- `/status`: shows the active forwarding mode, target chat, polling interval, and enabled sources without exposing secrets.

## LinkedIn Note

This project does not bypass LinkedIn restrictions or scrape LinkedIn directly. LinkedIn links can still be handled when a user forwards a post or sends a LinkedIn URL to the bot.

## LinkedIn User Posts

The bot can publish relevant LinkedIn user posts as `linkedin_user_post` results when the posts come from an allowed source. It does not log in to LinkedIn, automate a browser, or scrape LinkedIn pages.

To enable automated intake, provide a JSON feed produced by an official API, webhook, export, or external service that is allowed to supply LinkedIn post data:

```dotenv
ENABLE_LINKEDIN_USER_POSTS=true
LINKEDIN_USER_POSTS_FEED_URL=https://authorized.example/linkedin-posts.json
```

Leave `ENABLE_LINKEDIN_USER_POSTS=false` or keep `LINKEDIN_USER_POSTS_FEED_URL` empty to disable this source.

Accepted feed shape:

```json
{
  "posts": [
    {
      "url": "https://www.linkedin.com/feed/update/urn:li:activity:123/",
      "text": "We're hiring a React developer to join our team.",
      "published_at": "2026-07-07T07:30:00Z",
      "author": "Jane Hiring"
    }
  ]
}
```

The adapter also accepts a top-level JSON array, or list fields named `items`, `data`, or `results`.

LinkedIn post filtering requires:

- a LinkedIn URL;
- explicit hiring intent such as `we're hiring`, `looking for a backend engineer`, `need a UI/UX designer`, or `hiring React developer`;
- an allowed developer or designer role such as frontend, backend, fullstack, mobile, React, Vue, Angular, Node.js, Python, PHP, Java, UI/UX, product, or graphic designer.

The bot rejects candidate posts like `looking for job`, course ads, resumes, general hiring commentary, and posts without an explicit candidate-search intent. Duplicates are skipped through the same SQLite URL fingerprint store used for vacancies. Dated LinkedIn posts older than `SOURCE_MAX_AGE_HOURS` are skipped.
