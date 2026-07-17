# TG Vacancy Bot

Telegram bot for collecting IT vacancies from forwarded messages and public job sources, then publishing them to a target Telegram channel in a compact card format.

The planned profile and controlled application automation feature is documented in [`docs/application-automation-plan.md`](docs/application-automation-plan.md). The document contains the current implementation status, safety boundaries, staged architecture, and acceptance checks.

## What Works Now

- Accepts messages forwarded or sent to the bot.
- Publishes to a configured Telegram channel/group.
- Supports two forwarded-message modes:
  - `normalize`: parse text and publish a clean vacancy card.
  - `copy`: copy the original message to the target channel after the same allowed-vacancy intake check.
- Publishes only development/UI/UX/AI vacancies: backend, frontend, fullstack, UI/UX, LLM, AI, and clear software developer/engineer roles.
- Stores message fingerprints in SQLite to avoid duplicates.
- Includes Arbeitnow, Working Nomads, and opt-in LinkedIn hiring-post discovery. Arbeitnow supports verified form preparation; Working Nomads provides public vacancies with a manual employer-application link.
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

When the bot starts, it sends each configured operator whose profile is missing
a full name, email, or resume a private onboarding prompt with buttons to fill
in the fields and upload the resume. `/start` shows the same prompt until those
required application details are complete. An operator must have opened a
private chat with the bot first, because Telegram does not allow bots to start
a new chat with a user.

## Near-Real-Time Parser Mode

For an always-on vacancy parser, run the bot continuously with source polling enabled:

```dotenv
SOURCE_POLL_INTERVAL_SECONDS=60
SOURCE_MAX_AGE_HOURS=48
SOURCE_MAX_PUBLISH_PER_POLL=20
LINKEDIN_POST_MAX_AGE_HOURS=120
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
LINKEDIN_POST_SEARCH_RESULTS_WANTED=10
```

This source uses SerpApi or Serper Google Search results for publicly indexed LinkedIn post URLs worldwide. It publishes only real search results with a short snippet-based summary and the LinkedIn post link. Every LinkedIn result needs a reliable publication date and is rejected once it is older than `LINKEDIN_POST_MAX_AGE_HOURS` (maximum 120 hours). Use `||` to separate fallback search queries when you want the keyed provider to try several hiring-post searches. If neither `SERPAPI_API_KEY` nor `SERPER_API_KEY` is set, the source is not registered.

## Free LinkedIn Hiring Post Scraper

To avoid paid search APIs, enable the free scraper source:

```dotenv
ENABLE_LINKEDIN_POST_SCRAPER=true
LINKEDIN_POST_SCRAPER_QUERY=(site:linkedin.com/posts OR site:linkedin.com/feed/update) ("we are hiring" OR "we're hiring" OR hiring) (frontend OR backend OR fullstack OR "software developer" OR "software engineer" OR react OR python) || (site:linkedin.com/posts OR site:linkedin.com/feed/update) ("looking for" OR "join our team" OR "open role") (developer OR engineer OR frontend OR backend OR fullstack OR react OR python) || (site:linkedin.com/posts OR site:linkedin.com/feed/update) ("ищем" OR "ищет" OR "нанимаем" OR "в команду") (разработчик OR инженер OR frontend OR backend OR fullstack OR react OR python)
LINKEDIN_POST_SCRAPER_SEARCH_PROVIDERS=bing_rss,duckduckgo,bing
LINKEDIN_POST_SCRAPER_RESULTS_WANTED=100
```

This source reads public search results and keeps only real `linkedin.com/posts/...` and `linkedin.com/feed/update/...` links. It tries Bing RSS first, then public search-result HTML providers. It does not require an API key and does not create placeholder vacancies. Use `||` to separate fallback search queries. Because the HTML fallback depends on public search-result markup, it can be less stable than SerpApi and may return no rows when the search engine changes HTML or rate-limits requests. If an HTML provider returns a CAPTCHA or anti-bot page, the scraper skips that provider rather than bypassing the protection.

The scraper searches public, globally indexed results. It keeps only results with a reliable publication date (from the search result or the LinkedIn activity ID) and rejects posts older than `LINKEDIN_POST_MAX_AGE_HOURS` (maximum 120 hours) before they reach the common polling layer.
The search depth is intentionally larger than the per-cycle publication budget: SQLite deduplication lets later polls publish the remaining fresh posts. Every source vacancy is localized to Russian before publication.

## Headless LinkedIn Hiring Post Parser

The optional `LinkedInPostHeadlessAdapter` uses the project’s existing open-source [Playwright](https://github.com/microsoft/playwright-python) runtime to parse publicly indexed LinkedIn post pages in a clean headless browser context. For reliable link discovery, configure an existing SerpApi or Serper key; without one it falls back to Bing, which is best effort and can return no rows when blocked:

```dotenv
ENABLE_LINKEDIN_POST_HEADLESS=true
SERPAPI_API_KEY=your_key # or SERPER_API_KEY=your_key
LINKEDIN_POST_HEADLESS_QUERY=(site:linkedin.com/posts OR site:linkedin.com/feed/update) ("we are hiring" OR hiring OR "ищем" OR "ищет") (frontend OR backend OR developer OR engineer OR react OR python OR разработчик OR инженер)
LINKEDIN_POST_HEADLESS_RESULTS_WANTED=10
LINKEDIN_POST_HEADLESS_TIMEOUT_SECONDS=20
```

It discovers globally indexed public posts without a country restriction. It does not use a LinkedIn account, cookies, proxies, fake identities, scrolling automation, or any CAPTCHA/login/2FA bypass. It publishes only posts whose public page contains extractable text, whose activity URL has a reliable publication date, and whose date is no more than five days old. A login or protection page is skipped without a fallback vacancy. On GitHub Actions, enabling the source installs Chromium before polling.

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

Optional LinkedIn keys and toggles such as `SERPAPI_API_KEY`, `SERPER_API_KEY`, and
`ENABLE_LINKEDIN_POST_*` can also be configured as GitHub secrets. The workflow keeps `DATABASE_PATH` under
`data/` and restores it with the GitHub Actions cache so source deduplication is
preserved between scheduled runs.

Do not run the 15-minute GitHub Actions scheduler and a production always-on
server against the same Telegram channel at the same time unless they share the
same deduplication database. Otherwise, both schedulers can publish the same new
vacancy before either one sees the other's SQLite state.

The same workflow can process delayed `Откликнуться` callbacks without an
always-on server. Telegram keeps the callback until a scheduled runner invokes
`tg-vacancy-bot process-applications-once`; the runner downloads the configured
resume by Telegram `file_id`, first sends the operator a private confirmation
that the application is prepared, handles the application, sends a private
factual result, and exits. Send a PDF/DOCX to the bot with the `/queue_resume` caption once to
register or replace the queue resume without copying its `file_id` into GitHub.
This mode is opt-in and requires additional GitHub secrets. See
[`docs/application-queue.md`](docs/application-queue.md) for setup, usage,
privacy boundaries, expected delay, and the current JOIN/CAPTCHA limitation.

To check which sources are configured without publishing anything:

```powershell
tg-vacancy-bot check-sources
```

To fetch configured sources and preview filtered candidates without publishing anything:

```powershell
tg-vacancy-bot preview-sources --source "LinkedIn Hiring Posts" --limit 5
```

When `SOURCE_POLL_INTERVAL_SECONDS` is greater than `0`, `tg-vacancy-bot run` also polls configured public sources in the background while it listens for forwarded messages.
`SOURCE_MAX_PUBLISH_PER_POLL` limits how many source vacancies can be published in one polling cycle, which prevents first-run flooding. Source polling always attempts to localize descriptions before publication; if the provider fails, it logs the failure and publishes the original description and vacancy link instead.

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

This uses the real OpenAI API, or an OpenAI-compatible endpoint such as OpenRouter, for normalized cards from forwarded messages, `publish-message`, and all source polling. Source polling forces a localization attempt even when `LOCALIZE_DESCRIPTIONS=false`; that switch only affects manual-message flows. If the provider fails or its key is absent, source polling logs the error and publishes the real vacancy with its original description and link rather than dropping it.

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

- `/start`: for an incomplete operator profile, prompts to fill in fields and upload a resume; otherwise shows forwarding instructions.
- `/help`: shows forwarding instructions.
- `/whoami`: returns your Telegram user ID for `OPERATOR_USER_IDS`.
- `/status`: shows the active forwarding mode, target chat, polling interval, and enabled sources without exposing secrets.
- `/profile`: private operator profile: view/edit job preferences, upload or replace a resume, or delete the profile.
- `/queue_resume`: attach this caption to a PDF/DOCX sent privately while queue mode is active; the next GitHub Actions run registers or replaces the queue resume.
- `/queue_resume_id`: legacy private operator-only command that shows the saved Telegram `file_id`; it is no longer needed for normal queue setup.

Every normalized vacancy card now includes an `Откликнуться` button. It keeps
only a short vacancy ID in Telegram and resolves the original URL from SQLite;
the button is intentionally unavailable for `FORWARDED_MODE=copy`, because a
copied third-party message cannot safely receive the normalized card markup.
After the button is processed, the bot sends the operator a persistent private
`Отклик подготовлен` message and then a factual result message. It says
`Отклик отправлен` only for a confirmed `submitted` status; prepared, manual,
incomplete-profile, cancelled, and failed attempts are explicitly reported as
not sent. The operator must have opened the bot's private chat first so Telegram
can deliver these notifications.

## Arbeitnow application form

The first supported form is Arbeitnow's public application page. Put
`APPLICATION_ALLOWED_DOMAINS=arbeitnow.com` in `.env`, complete `/profile` with a
first and last name, email, and PDF/DOCX resume, then press `Откликнуться` on an
Arbeitnow card. The always-on bot fills only the verified fields and uploads the
local resume, then stops before final submit. The opt-in GitHub Actions queue can
submit only a verified direct Arbeitnow form and reports success only after a
recognized success page. Current Arbeitnow vacancies commonly redirect to JOIN,
which requires email authentication and reCAPTCHA; that path stops for manual
action and is never reported as submitted.

## Working Nomads source

Working Nomads is enabled by default through its public JSON feed:

```dotenv
ENABLE_WORKING_NOMADS=true
```

The source needs no API key or Working Nomads account. Its `Откликнуться` button
stores the application attempt and sends the operator a link that redirects to
the employer's actual form. The bot does not auto-fill or submit these varied
external forms; a future adapter must be implemented and verified for each ATS
or employer form separately.

## LinkedIn Boundary

This project permits three documented, opt-in LinkedIn paths: keyed Google Search-backed public hiring-post search through SerpApi or Serper, free public search-result scraping, and headless parsing of publicly available post pages found through Bing. It does not log in with a LinkedIn account, use proxies or anti-bot bypasses, invent vacancies, or publish fake fallback records when LinkedIn or a search provider blocks or returns no results.

LinkedIn links can also enter when an operator manually sends or forwards vacancy text containing a LinkedIn URL to the Telegram bot. In that case the normal forwarded-message parser can keep the URL and mark the vacancy source as `LinkedIn`.
