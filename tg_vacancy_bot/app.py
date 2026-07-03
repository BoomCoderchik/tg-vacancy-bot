from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from collections.abc import Sequence

from .bot import run_bot_sync
from .config import get_settings
from .publisher import TelegramPublisher
from .sources import build_adapters, filter_it_vacancies
from .storage import VacancyStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tg-vacancy-bot")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("run", help="Run Telegram bot polling.")
    subparsers.add_parser("poll-once", help="Poll public sources once and publish new vacancies.")
    return parser


async def poll_once() -> None:
    settings = get_settings()
    settings.require_runtime()
    logging.basicConfig(level=logging.INFO)
    store = VacancyStore(settings.database_path)
    publisher = TelegramPublisher(settings, store)

    try:
        total = 0
        published = 0
        for adapter in build_adapters(settings):
            try:
                vacancies = await adapter.fetch()
            except Exception:
                logging.exception("%s: source fetch failed", adapter.name)
                continue
            filtered = filter_it_vacancies(vacancies)
            total += len(filtered)
            published += await publisher.publish_new(filtered)
            logging.info("%s: fetched=%s filtered=%s", adapter.name, len(vacancies), len(filtered))
        logging.info("Done. candidates=%s published=%s", total, published)
    finally:
        await publisher.close()


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    settings = get_settings()

    try:
        if args.command == "run":
            run_bot_sync(settings)
            return

        if args.command == "poll-once":
            asyncio.run(poll_once())
            return
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc

    raise SystemExit(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
