# TG Vacancy Bot

Telegram bot for collecting IT vacancies from forwarded messages and public job sources, then publishing them to a target Telegram channel in a compact card format.

## What Works Now

- Accepts messages forwarded or sent to the bot.
- Publishes to a configured Telegram channel/group.
- Supports two forwarded-message modes:
  - `normalize`: parse text and publish a clean vacancy card.
  - `copy`: copy the original message to the target channel.
- Stores message fingerprints in SQLite to avoid duplicates.
- Includes initial source adapters for Remotive, Arbeitnow, RemoteOK, and Hacker News "Who is Hiring".
- Polls configured public sources in the background while the bot is running.

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

To preview how a forwarded vacancy will be normalized before posting:

```powershell
Get-Content .\sample-message.txt -Raw | tg-vacancy-bot preview-message
```

Or:

```powershell
tg-vacancy-bot preview-message --file .\sample-message.txt
```

## Forwarded Message Flow

Send or forward a vacancy message to the bot. In `normalize` mode, the bot will publish a card like:

```text
IT Job Board
💼 Senior Full-Stack Engineer

📍 Локация: Удаленно

🧠 Стек: Python, FastAPI, React, AWS

Описание:
...

🔗 Смотреть вакансию
```

In `copy` mode, the bot copies the original message to the target channel.

In `normalize` mode, messages that do not look like IT vacancies are skipped. Use `copy` mode if you want every forwarded message to be copied as-is.

## Bot Commands

- `/start` or `/help`: shows the forwarding instructions.
- `/whoami`: returns your Telegram user ID for `OPERATOR_USER_IDS`.
- `/status`: shows the active forwarding mode, target chat, polling interval, and enabled sources without exposing secrets.

## LinkedIn Note

This project does not bypass LinkedIn restrictions or scrape LinkedIn directly. LinkedIn links can still be handled when a user forwards a post or sends a LinkedIn URL to the bot.
