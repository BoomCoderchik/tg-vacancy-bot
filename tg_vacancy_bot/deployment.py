from __future__ import annotations

import asyncio
import hmac
import logging
import os
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from aiohttp import web

from .bot import run_bot
from .config import Settings
from .linkedin_posts import build_linkedin_user_post_vacancy, extract_linkedin_user_post_records
from .models import Vacancy
from .publisher import TelegramPublisher
from .sources import filter_it_vacancies
from .storage import VacancyStore


logger = logging.getLogger(__name__)
Publisher = Callable[[list[Vacancy]], Awaitable[int]]
SETTINGS_KEY = web.AppKey("settings", Settings)
LINKEDIN_USER_POSTS_PUBLISHER_KEY = web.AppKey("linkedin_user_posts_publisher", Publisher)


def get_port(default: int = 8080) -> int:
    raw_port = os.getenv("PORT", str(default))
    try:
        return int(raw_port)
    except ValueError as exc:
        raise RuntimeError(f"PORT must be an integer, got {raw_port!r}") from exc


async def health(_request: web.Request) -> web.Response:
    return web.json_response({"status": "ok"})


async def publish_linkedin_user_posts(request: web.Request) -> web.Response:
    settings = request.app[SETTINGS_KEY]
    if not settings.linkedin_user_posts_webhook_token:
        return web.json_response({"error": "linkedin webhook is not enabled"}, status=404)

    if not _is_authorized(request, settings.linkedin_user_posts_webhook_token):
        return web.json_response({"error": "unauthorized"}, status=401)

    try:
        payload = await request.json()
    except ValueError:
        return web.json_response({"error": "invalid json"}, status=400)

    now = datetime.now(UTC)
    records = extract_linkedin_user_post_records(payload)
    vacancies = [
        vacancy
        for record in records
        if (
            vacancy := build_linkedin_user_post_vacancy(
                record,
                now=now,
                max_age_hours=settings.source_max_age_hours,
            )
        )
    ]
    vacancies = filter_it_vacancies(vacancies)
    publisher = request.app[LINKEDIN_USER_POSTS_PUBLISHER_KEY]

    try:
        published = await publisher(vacancies)
    except RuntimeError as exc:
        logger.warning("LinkedIn user-post webhook publication failed: %s", exc)
        return web.json_response({"error": str(exc)}, status=502)

    return web.json_response(
        {
            "received": len(records),
            "accepted": len(vacancies),
            "published": published,
        }
    )


def _is_authorized(request: web.Request, token: str) -> bool:
    header = request.headers.get("Authorization", "")
    bearer_prefix = "Bearer "
    supplied = ""
    if header.startswith(bearer_prefix):
        supplied = header[len(bearer_prefix) :].strip()
    else:
        supplied = request.headers.get("X-Webhook-Token", "").strip()
    return bool(supplied) and hmac.compare_digest(supplied, token)


async def publish_with_telegram(settings: Settings, vacancies: list[Vacancy]) -> int:
    if not vacancies:
        return 0
    store = VacancyStore(settings.database_path)
    publisher = TelegramPublisher(settings, store)
    try:
        return await publisher.publish_new(vacancies)
    finally:
        await publisher.close()


def create_web_app(settings: Settings, publisher: Publisher | None = None) -> web.Application:
    app = web.Application()
    app[SETTINGS_KEY] = settings
    app[LINKEDIN_USER_POSTS_PUBLISHER_KEY] = publisher or (
        lambda vacancies: publish_with_telegram(settings, vacancies)
    )
    app.router.add_get("/", health)
    app.router.add_get("/health", health)
    app.router.add_post("/linkedin/user-posts", publish_linkedin_user_posts)
    return app


async def run_web_service(settings: Settings, host: str = "0.0.0.0", port: int | None = None) -> None:
    settings.require_runtime()

    app = create_web_app(settings)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host=host, port=port or get_port())
    await site.start()

    bot_task = asyncio.create_task(run_bot(settings))
    try:
        await bot_task
    finally:
        await runner.cleanup()


def run_web_service_sync(settings: Settings) -> None:
    asyncio.run(run_web_service(settings))
