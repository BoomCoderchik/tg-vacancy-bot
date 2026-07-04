# Deployment

This project must run as a real Telegram vacancy aggregator. Do not deploy it with
fake Telegram publishing, fake source results, or placeholder vacancies.

## Recommended Free Path: Koyeb Web Service

The bot is a long-running process, so use:

```bash
tg-vacancy-bot run-web
```

This starts the normal Telegram long polling and background source polling, plus
an HTTP health endpoint:

- `GET /`
- `GET /health`

The endpoint exists so free web hosts can route traffic to the process and so an
external uptime monitor can keep the service active.

### Koyeb Settings

- Deployment type: Dockerfile
- Instance: Free
- Region: Frankfurt or Washington, D.C.
- Port: use Koyeb's detected `$PORT`
- Run command: leave empty if the Dockerfile is used, or set `tg-vacancy-bot run-web`
- Health check path: `/health`

Add environment variables from `.env` in the Koyeb dashboard. Do not commit `.env`.

Required:

```dotenv
TELEGRAM_BOT_TOKEN=...
TARGET_CHAT_ID=...
OPERATOR_USER_IDS=...
FORWARDED_MODE=normalize
DATABASE_PATH=data/vacancies.sqlite3
SOURCE_POLL_INTERVAL_SECONDS=900
SOURCE_MAX_PUBLISH_PER_POLL=20
```

Source toggles:

```dotenv
ENABLE_REMOTIVE=true
ENABLE_ARBEITNOW=true
ENABLE_REMOTEOK=true
ENABLE_HN_WHO_IS_HIRING=true
```

Optional keyed sources:

```dotenv
ADZUNA_APP_ID=
ADZUNA_APP_KEY=
JOOBLE_API_KEY=
```

Optional localization:

```dotenv
LOCALIZE_DESCRIPTIONS=false
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4.1-mini
OPENAI_BASE_URL=
```

### Keep-Alive

Koyeb Free web services can scale to zero when they receive no traffic. Configure
a free uptime monitor, such as UptimeRobot or cron-job.org, to request:

```text
https://<your-koyeb-service>.koyeb.app/health
```

Use an interval shorter than the provider's idle timeout.

## Production Caveat

The current deduplication store is SQLite. On free web services without a
persistent volume, the local SQLite file can be lost on restarts, redeploys, or
scale-to-zero events. If this happens, old vacancies may be published again until
the store is rebuilt.

For stronger production behavior, use a paid service with persistent disk or add
a real external database-backed `VacancyStore`. Do not replace this with an
in-memory store or demo data.
