# TG Vacancy Bot

Telegram bot for collecting IT vacancies from forwarded messages and public job sources, then publishing them to a target Telegram channel in a compact card format.

The planned profile and controlled application automation feature is documented in [`docs/application-automation-plan.md`](docs/application-automation-plan.md). The document contains the current implementation status, safety boundaries, staged architecture, and acceptance checks.

## What Works Now

- Accepts messages forwarded or sent to the bot.
- Publishes to a configured Telegram channel/group.
- Supports two forwarded-message modes:
  - `normalize`: parse text and publish a clean vacancy card.
  - `copy`: copy the original message to the target channel after the same allowed-vacancy intake check.
- Publishes only development/design/AI vacancies: backend, frontend, fullstack, design, LLM, AI, and clear software developer/engineer roles.
- Stores message fingerprints in SQLite to avoid duplicates.
- Includes source adapters for Remotive, Arbeitnow, RemoteOK, Hacker News "Who is Hiring", Jobicy, We Work Remotely, Himalayas, Real Work From Anywhere, JobsCollider, Adzuna, Jooble, opt-in LinkedIn hiring-post search, opt-in free LinkedIn hiring-post scraping, and opt-in JobSpy LinkedIn Jobs discovery.
- Polls configured public sources in the background while the bot is running.

## Profile storage foundation

The first foundation stage for the private operator profile is available in the
application storage layer. It persists one profile per Telegram operator, with
contact and job-preference fields plus extensible fields. Original PDF/DOCX
resumes are stored only in a local directory (not in Git, logs, or the public
channel). Configure it with:

```dotenv
RESUME_STORAGE_DIR=data/resumes
RESUME_MAX_SIZE_BYTES=10485760
```

Use `/profile` in a private chat with the bot to view the profile, fill in
fields step by step, upload or replace a PDF/DOCX resume, and delete the
profile. This command requires an explicit `OPERATOR_USER_IDS` allowlist;
unlisted users cannot read or change this private data. Extracting resume text
is scheduled for the next task in the implementation plan.

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

To find ordinary LinkedIn posts like "Ищем Junior Front-End Developer..." rather than LinkedIn Jobs cards, enable the Google Search-backed post search source through [SerpApi](https://serpapi.com/search-api) or [Serper](https://serper.dev/):

```dotenv
ENABLE_LINKEDIN_POST_SEARCH=true
SERPAPI_API_KEY=
# Or use Serper instead of SerpApi:
SERPER_API_KEY=
LINKEDIN_POST_SEARCH_QUERY=(site:linkedin.com/posts OR site:linkedin.com/feed/update) ("we are hiring" OR "we're hiring" OR hiring OR "looking for" OR "join our team" OR "open role" OR "ищем" OR "ищет" OR "нанимаем" OR "в команду") (frontend OR "front-end" OR backend OR fullstack OR "full-stack" OR "software developer" OR "software engineer" OR developer OR engineer OR react OR python OR designer OR "AI engineer" OR "ML engineer" OR "LLM engineer" OR разработчик OR инженер)
LINKEDIN_POST_SEARCH_LOCATION=Kazakhstan
LINKEDIN_POST_SEARCH_RESULTS_WANTED=10
```

This source uses SerpApi or Serper Google Search results for publicly indexed LinkedIn post URLs. It publishes only real search results with a short snippet-based summary and the LinkedIn post link. Use `||` to separate fallback search queries when you want the keyed provider to try several hiring-post searches. If neither `SERPAPI_API_KEY` nor `SERPER_API_KEY` is set, the source is not registered.

## Free LinkedIn Hiring Post Scraper

To avoid paid search APIs, enable the free scraper source:

```dotenv
ENABLE_LINKEDIN_POST_SCRAPER=true
LINKEDIN_POST_SCRAPER_QUERY=(site:linkedin.com/posts OR site:linkedin.com/feed/update) ("we are hiring" OR "we're hiring" OR hiring) (frontend OR backend OR fullstack OR "software developer" OR "software engineer" OR react OR python) || (site:linkedin.com/posts OR site:linkedin.com/feed/update) ("looking for" OR "join our team" OR "open role") (developer OR engineer OR frontend OR backend OR fullstack OR react OR python) || (site:linkedin.com/posts OR site:linkedin.com/feed/update) ("ищем" OR "ищет" OR "нанимаем" OR "в команду") (разработчик OR инженер OR frontend OR backend OR fullstack OR react OR python)
LINKEDIN_POST_SCRAPER_LOCATION=Kazakhstan
LINKEDIN_POST_SCRAPER_RESULTS_WANTED=100
```

This source scrapes public search-result HTML and keeps only real `linkedin.com/posts/...` and `linkedin.com/feed/update/...` links. It does not require an API key and does not create placeholder vacancies. Use `||` to separate fallback search queries. Because it depends on public search-result markup, it can be less stable than SerpApi and may return no rows when the search engine changes HTML or rate-limits requests.

The scraper keeps only results with a reliable publication date (from the search result or the LinkedIn activity ID) and the normal `SOURCE_MAX_AGE_HOURS` freshness filter removes older posts before publishing.
The search depth is intentionally larger than the per-cycle publication budget: SQLite deduplication lets later polls publish the remaining fresh posts. `LOCALIZATION_MAX_PER_POLL=12` caps localization attempts per poll when localization is enabled; lower it further if the provider is rate-limited.

## JobSpy LinkedIn Jobs Discovery

LinkedIn Jobs discovery is available as an explicit opt-in source through [JobSpy](https://github.com/speedyapply/JobSpy). It is intended to send new LinkedIn Jobs links in the configured development/design/AI search scope through the same source polling flow as the other adapters: intake filter, freshness filter, SQLite deduplication, publication limit, and Telegram publishing.

Enable it only when you accept LinkedIn's operational risk around automated access:

```dotenv
ENABLE_JOBSPY_LINKEDIN=false
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

## Scheduled Parsing Without A Running Server

This repository includes `.github/workflows/scheduled-source-polling.yml`, which runs
`tg-vacancy-bot poll-once` on GitHub Actions every 15 minutes. This lets new
source vacancies be parsed and published to Telegram even when your local
server or laptop is off.

Configure the required repository secrets in GitHub before enabling production
use:

- `TELEGRAM_BOT_TOKEN`
- `TARGET_CHAT_ID`
- One localization key when `LOCALIZE_DESCRIPTIONS=true`: `OPENAI_API_KEY` for the default mode, or `GROQ_API_KEY` when `LOCALIZATION_PROVIDER=groq`.

Optional source API keys and toggles such as `ADZUNA_APP_ID`,
`ADZUNA_APP_KEY`, `JOOBLE_API_KEY`, `SERPAPI_API_KEY`, `SERPER_API_KEY`, and `ENABLE_*` can also
be configured as GitHub secrets. The workflow keeps `DATABASE_PATH` under
`data/` and restores it with the GitHub Actions cache so source deduplication is
preserved between scheduled runs.

Do not run the 15-minute GitHub Actions scheduler and a production always-on
server against the same Telegram channel at the same time unless they share the
same deduplication database. Otherwise, both schedulers can publish the same new
vacancy before either one sees the other's SQLite state.

To check which sources are configured without publishing anything:

```powershell
tg-vacancy-bot check-sources
```

To fetch configured sources and preview filtered candidates without publishing anything:

```powershell
tg-vacancy-bot preview-sources --source "LinkedIn Hiring Posts" --limit 5
```

When `SOURCE_POLL_INTERVAL_SECONDS` is greater than `0`, `tg-vacancy-bot run` also polls configured public sources in the background while it listens for forwarded messages.
`SOURCE_MAX_PUBLISH_PER_POLL` limits how many source vacancies can be published in one polling cycle, which prevents first-run flooding. When localization is enabled, `LOCALIZATION_MAX_PER_POLL` separately limits model calls; unlocalized posts remain available for a later poll through deduplication.

For web-hosting deployment, use:

```powershell
tg-vacancy-bot run-web
```

This runs the same Telegram bot and source polling loop with `GET /` and `GET /health` endpoints for platforms that require an open port. For reliable always-on parsing, prefer the VM path in `docs/deployment.md`.

## Description Localization

To translate vacancy descriptions into Russian and compress long source text before publishing, set:

```dotenv
LOCALIZE_DESCRIPTIONS=true
LOCALIZATION_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4.1-mini
OPENAI_FALLBACK_MODELS=
OPENAI_BASE_URL=
```

This uses the real OpenAI API, or an OpenAI-compatible endpoint such as OpenRouter, for normalized cards from forwarded messages, `publish-message`, and public source polling. If localization is enabled without the selected provider key, publishing stops with a clear configuration error instead of using fake or placeholder text.

### Free Groq localization mode

For the scheduled parser's current load profile, Groq is the supported free option:

```dotenv
LOCALIZE_DESCRIPTIONS=true
LOCALIZATION_PROVIDER=groq
GROQ_API_KEY=gsk_...
# Defaults shown explicitly; change these only after testing a replacement model.
GROQ_MODEL=llama-3.1-8b-instant
GROQ_FALLBACK_MODELS=openai/gpt-oss-20b
```

Groq is OpenAI-client-compatible, so the bot uses its API directly rather than the unstable OpenRouter free-model pool. At the time this was documented, the free limit for `llama-3.1-8b-instant` is 30 requests/minute and 14,400 requests/day: above the bot's 20-vacancy, 15-minute poll ceiling. Groq has announced that this particular model will be removed on 2026-08-16; the configured `openai/gpt-oss-20b` fallback keeps the bot running, but has a lower free quota. Before that date, test and set a replacement through `GROQ_MODEL` and `GROQ_FALLBACK_MODELS` without changing code. Add `LOCALIZATION_PROVIDER=groq`, `GROQ_API_KEY`, and optionally the two model variables as GitHub Actions secrets; do not store the key in the repository.

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
- `/profile`: private operator profile: view/edit job preferences, upload or replace a resume, or delete the profile.

## LinkedIn Boundary

This project now permits three documented, opt-in LinkedIn paths: keyed Google Search-backed public hiring-post search through SerpApi or Serper, free public search-result scraping for hiring posts, and JobSpy-backed LinkedIn Jobs discovery. It does not log in with a LinkedIn account, invent vacancies, or publish fake fallback records when LinkedIn or a search provider blocks or returns no results.

LinkedIn links can also enter when an operator manually sends or forwards vacancy text containing a LinkedIn URL to the Telegram bot. In that case the normal forwarded-message parser can keep the URL and mark the vacancy source as `LinkedIn`.
