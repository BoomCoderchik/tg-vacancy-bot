from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from collections.abc import Sequence
from datetime import UTC, datetime

from .bot import run_bot_sync
from .console import write_stdout
from .config import get_settings
from .deployment import run_web_service_sync
from .env_setup import init_env_file
from .preview import parse_publishable_message, preview_message_card_async
from .publisher import TelegramPublisher
from .sources import build_adapters, filter_it_vacancies, source_configuration_warnings
from .sources.freshness import filter_fresh_vacancies
from .storage import VacancyStore
from .telegram_check import check_telegram_access, format_check_result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="tg-vacancy-bot")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("run", help="Run Telegram bot polling.")
    subparsers.add_parser("run-web", help="Run Telegram bot polling with an HTTP health endpoint.")
    subparsers.add_parser("init-env", help="Create .env from .env.example without overwriting an existing file.")
    subparsers.add_parser("poll-once", help="Poll public sources once and publish new vacancies.")
    subparsers.add_parser("check-sources", help="Check source adapter configuration without publishing.")
    preview_sources_parser = subparsers.add_parser(
        "preview-sources",
        help="Fetch configured sources and print filtered candidates without publishing.",
    )
    preview_sources_parser.add_argument("--source", help="Preview only the source with this exact adapter name.")
    preview_sources_parser.add_argument("--limit", type=int, default=5, help="Maximum candidates to print per source.")
    subparsers.add_parser("check-telegram", help="Validate bot token, target chat access, and posting permissions.")
    preview_parser = subparsers.add_parser("preview-message", help="Parse message text and print the Telegram card HTML.")
    preview_parser.add_argument("--file", help="Read message text from a UTF-8 file instead of stdin.")
    publish_parser = subparsers.add_parser("publish-message", help="Publish one normalized vacancy from UTF-8 text.")
    publish_parser.add_argument("--file", required=True, help="Read message text from a UTF-8 file.")
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
        max_publish = settings.source_max_publish_per_poll
        for warning in source_configuration_warnings(settings):
            logging.warning(warning)
        for adapter in build_adapters(settings):
            if max_publish > 0 and published >= max_publish:
                logging.info("Source poll publish limit reached: %s", max_publish)
                break
            try:
                vacancies = await adapter.fetch()
            except Exception:
                logging.exception("%s: source fetch failed", adapter.name)
                continue
            filtered = filter_fresh_vacancies(
                filter_it_vacancies(vacancies),
                max_age_hours=settings.source_max_age_hours,
                current_time=datetime.now(UTC),
            )
            total += len(filtered)
            remaining = max_publish - published if max_publish > 0 else len(filtered)
            publishable = filtered[:remaining]
            for vacancy in publishable:
                try:
                    published += await publisher.publish_new([vacancy])
                except RuntimeError as exc:
                    logging.warning(
                        "%s: publication skipped for %r: %s",
                        adapter.name,
                        vacancy.title,
                        exc,
                    )
            logging.info("%s: fetched=%s filtered=%s", adapter.name, len(vacancies), len(filtered))
        logging.info("Done. candidates=%s published=%s", total, published)
    finally:
        await publisher.close()


async def publish_message_file(file_path: str) -> int:
    settings = get_settings()
    settings.require_runtime()
    store = VacancyStore(settings.database_path)
    publisher = TelegramPublisher(settings, store)
    text = Path(file_path).read_text(encoding="utf-8")
    try:
        return await publisher.publish_new([parse_publishable_message(text)])
    finally:
        await publisher.close()


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    settings = get_settings()

    try:
        if args.command == "run":
            run_bot_sync(settings)
            return

        if args.command == "run-web":
            run_web_service_sync(settings)
            return

        if args.command == "init-env":
            write_stdout(init_env_file())
            return

        if args.command == "poll-once":
            asyncio.run(poll_once())
            return

        if args.command == "check-sources":
            write_stdout(format_source_check(settings))
            return

        if args.command == "preview-sources":
            write_stdout(asyncio.run(preview_sources(settings, source_name=args.source, limit=args.limit)))
            return

        if args.command == "check-telegram":
            result = asyncio.run(check_telegram_access(settings))
            write_stdout(format_check_result(result))
            return

        if args.command == "preview-message":
            text = Path(args.file).read_text(encoding="utf-8") if args.file else sys.stdin.read()
            write_stdout(asyncio.run(preview_message_card_async(text, settings)))
            return

        if args.command == "publish-message":
            count = asyncio.run(publish_message_file(args.file))
            write_stdout(f"Published: {count}")
            return
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc

    raise SystemExit(f"Unknown command: {args.command}")


def format_source_check(settings) -> str:
    warnings = source_configuration_warnings(settings)
    adapter_names = [adapter.name for adapter in build_adapters(settings)]
    warning_lines = ["Warnings: none"] if not warnings else ["Warnings:", *[f"WARNING: {warning}" for warning in warnings]]
    return "\n".join(
        [
            "Source configuration",
            *warning_lines,
            "Registered adapters: " + (", ".join(adapter_names) if adapter_names else "none"),
        ]
    )


async def preview_sources(settings, source_name: str | None = None, limit: int = 5) -> str:
    lines = ["Source preview"]
    lines.extend(f"WARNING: {warning}" for warning in source_configuration_warnings(settings))
    adapters = build_adapters(settings)
    if source_name:
        adapters = [adapter for adapter in adapters if adapter.name == source_name]
    if not adapters:
        lines.append("No matching registered adapters.")
        return "\n".join(lines)

    per_source_limit = max(limit, 0)
    for adapter in adapters:
        try:
            vacancies = await adapter.fetch()
        except Exception as exc:
            lines.append(f"{adapter.name}: fetch failed: {exc}")
            continue
        filtered = filter_it_vacancies(vacancies)
        lines.append(f"{adapter.name}: fetched={len(vacancies)} filtered={len(filtered)}")
        for vacancy in filtered[:per_source_limit]:
            lines.append(f"- {vacancy.title}")
            if vacancy.url:
                lines.append(f"  {vacancy.url}")
    return "\n".join(lines)


if __name__ == "__main__":
    main()
