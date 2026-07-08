from __future__ import annotations

import asyncio
import os

from aiohttp import web

from .bot import run_bot
from .config import Settings


SETTINGS_KEY = web.AppKey("settings", Settings)


def get_port(default: int = 8080) -> int:
    raw_port = os.getenv("PORT", str(default))
    try:
        return int(raw_port)
    except ValueError as exc:
        raise RuntimeError(f"PORT must be an integer, got {raw_port!r}") from exc


async def health(_request: web.Request) -> web.Response:
    return web.json_response({"status": "ok"})


def create_web_app(settings: Settings) -> web.Application:
    app = web.Application()
    app[SETTINGS_KEY] = settings
    app.router.add_get("/", health)
    app.router.add_get("/health", health)
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
