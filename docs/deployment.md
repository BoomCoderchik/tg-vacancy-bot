# Deployment

This project must run as a real Telegram vacancy aggregator. Do not deploy it
with fake Telegram publishing, fake source results, in-memory demo fallbacks, or
placeholder vacancies.

## Recommended Free Path: Always-On VM

Use a free VM for the primary production setup:

- Google Cloud Free Tier `e2-micro` VM.
- Oracle Cloud Always Free VM.

A VM is a better default than free web services for this bot because it can run
as a real long-lived process, keep its SQLite database on persistent disk, and
poll sources every 60 seconds without relying on web traffic.

Recommended production source settings:

```dotenv
DATABASE_PATH=data/vacancies.sqlite3
SOURCE_POLL_INTERVAL_SECONDS=60
SOURCE_MAX_PUBLISH_PER_POLL=20
SOURCE_MAX_AGE_HOURS=48
LINKEDIN_POST_MAX_AGE_HOURS=120
```

Sixty-second polling is near-real-time for ordinary job APIs. Instant delivery
is only possible when a source provides a webhook or stream.

## Ubuntu VM Setup

Install system packages:

```bash
sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip git
```

Clone the repository and install the bot:

```bash
git clone <your-repo-url> tg-vacancy-bot
cd tg-vacancy-bot
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
```

Create `.env` from `.env.example` and fill real credentials:

```bash
cp .env.example .env
nano .env
```

Required:

```dotenv
TELEGRAM_BOT_TOKEN=...
TARGET_CHAT_ID=...
OPERATOR_USER_IDS=...
FORWARDED_MODE=normalize
DATABASE_PATH=data/vacancies.sqlite3
SOURCE_POLL_INTERVAL_SECONDS=60
SOURCE_MAX_PUBLISH_PER_POLL=20
SOURCE_MAX_AGE_HOURS=48
LINKEDIN_POST_MAX_AGE_HOURS=120
```

Validate the real Telegram integration before starting the service:

```bash
.venv/bin/tg-vacancy-bot check-telegram
```

Run manually once to confirm startup:

```bash
.venv/bin/tg-vacancy-bot run
```

Stop it with `Ctrl+C` after confirming it starts. Then configure systemd.

## systemd Service

Create `/etc/systemd/system/tg-vacancy-bot.service`:

```ini
[Unit]
Description=TG Vacancy Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/home/ubuntu/tg-vacancy-bot
EnvironmentFile=/home/ubuntu/tg-vacancy-bot/.env
ExecStart=/home/ubuntu/tg-vacancy-bot/.venv/bin/tg-vacancy-bot run
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Adjust `WorkingDirectory`, `EnvironmentFile`, and `ExecStart` if you cloned the
repo somewhere else or use a different Linux user.

Enable and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable tg-vacancy-bot
sudo systemctl start tg-vacancy-bot
sudo systemctl status tg-vacancy-bot
```

Watch logs:

```bash
journalctl -u tg-vacancy-bot -f
```

SQLite should stay on the VM persistent disk, for example
`DATABASE_PATH=data/vacancies.sqlite3`. Do not place it on ephemeral storage.

## Optional Web-Service Fallback

`tg-vacancy-bot run-web` exists for platforms that require an HTTP port:

```bash
tg-vacancy-bot run-web
```

It starts the same Telegram bot and source polling loop plus:

- `GET /`
- `GET /health`

Koyeb Free can be useful for quick experiments, but it can scale to zero. That
can delay near-real-time polling and can lose SQLite state if no persistent disk
is available. Render Free has similar sleep behavior and is not recommended as
the primary always-on parser path.

For polling that must continue when no server is running, use the GitHub Actions
schedule below. Prefer the VM path when you need a true always-on bot process,
forwarded-message handling, or tighter polling than 15 minutes.

## Serverless Scheduled Polling: GitHub Actions

If you want parsing to continue after your local server or laptop is turned off,
use the included GitHub Actions scheduler:

```text
.github/workflows/scheduled-source-polling.yml
```

It runs `tg-vacancy-bot poll-once` every 15 minutes and publishes only real,
deduplicated vacancies to `TARGET_CHAT_ID`. This is the simplest no-server path
for 15-minute polling. It is not a true always-on bot process, so forwarded
Telegram messages are not handled while no server is running, and GitHub may
delay scheduled jobs during platform load.

Required GitHub repository secrets:

- `TELEGRAM_BOT_TOKEN`
- `TARGET_CHAT_ID`

Set these only if the matching LinkedIn feature is enabled:

- `SERPAPI_API_KEY` or `SERPER_API_KEY` when `ENABLE_LINKEDIN_POST_SEARCH=true`

Optional secrets can override defaults, including `SOURCE_MAX_PUBLISH_PER_POLL`,
`SOURCE_MAX_AGE_HOURS`, `ENABLE_LINKEDIN_POST_SCRAPER`, and
`ENABLE_LINKEDIN_POST_HEADLESS`. Source polling always leaves translation
disabled. When the headless source is enabled, the
scheduled workflow installs Chromium before polling.

The workflow stores the SQLite deduplication database in `data/` and restores it
through the GitHub Actions cache. Keep only one production scheduler active for
the same Telegram channel unless all schedulers share the same database; a VM
service and GitHub Actions cache do not share state and can duplicate posts.
