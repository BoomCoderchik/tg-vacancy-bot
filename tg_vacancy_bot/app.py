from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from collections.abc import Sequence

from .bot import run_bot_sync
from .console import write_stdout
from .config import get_settings
from .env_setup import init_env_file
from .preview import preview_message_card
from .publisher import TelegramPublisher
from .sources import build_adapters, filter_it_vacancies
from .storage import VacancyStore
from .telegram_check import check_telegram_access, format_check_result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tg-vacancy-bot")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("run", help="Run Telegram bot polling.")
    subparsers.add_parser("init-env", help="Create .env from .env.example without overwriting an existing file.")
    subparsers.add_parser("poll-once", help="Poll public sources once and publish new vacancies.")
    subparsers.add_parser("check-telegram", help="Validate bot token, target chat access, and posting permissions.")
    preview_parser = subparsers.add_parser("preview-message", help="Parse message text and print the Telegram card HTML.")
    preview_parser.add_argument("--file", help="Read message text from a UTF-8 file instead of stdin.")
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

        if args.command == "init-env":
            write_stdout(init_env_file())
            return

        if args.command == "poll-once":
            asyncio.run(poll_once())
            return

        if args.command == "check-telegram":
            result = asyncio.run(check_telegram_access(settings))
            write_stdout(format_check_result(result))
            return

        if args.command == "preview-message":
            text = Path(args.file).read_text(encoding="utf-8") if args.file else sys.stdin.read()
            write_stdout(preview_message_card(text))
            return
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc

    raise SystemExit(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
