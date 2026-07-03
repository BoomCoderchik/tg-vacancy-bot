from __future__ import annotations

import asyncio
import logging
from dataclasses import replace

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message

from .config import Settings
from .formatting import format_vacancy_card
from .intake import looks_like_vacancy_message
from .parser import parse_message_to_vacancy
from .source_polling import poll_sources_forever
from .storage import VacancyStore
from .telegram_origin import forwarded_public_post_url

logger = logging.getLogger(__name__)


def build_status_text(settings: Settings) -> str:
    source_states = [
        f"Remotive={'on' if settings.enable_remotive else 'off'}",
        f"Arbeitnow={'on' if settings.enable_arbeitnow else 'off'}",
        f"RemoteOK={'on' if settings.enable_remoteok else 'off'}",
        f"HN={'on' if settings.enable_hn_who_is_hiring else 'off'}",
        f"Adzuna={'on' if settings.adzuna_app_id and settings.adzuna_app_key else 'off'}",
        f"Jooble={'on' if settings.jooble_api_key else 'off'}",
    ]
    return "\n".join(
        [
            "TG Vacancy Bot status",
            f"Forwarded mode: {settings.forwarded_mode}",
            f"Target chat: {settings.target_chat_id or 'not configured'}",
            f"Source polling interval: {settings.source_poll_interval_seconds}s",
            "Sources: " + ", ".join(source_states),
        ]
    )


def create_dispatcher(settings: Settings, store: VacancyStore) -> Dispatcher:
    dp = Dispatcher()

    @dp.message(Command("start", "help"))
    async def start(message: Message) -> None:
        await message.answer(
            "Пришли или перешли мне вакансию. Я опубликую ее в целевой канал "
            "как карточку или скопирую оригинал, в зависимости от FORWARDED_MODE."
        )

    @dp.message(Command("status"))
    async def status(message: Message) -> None:
        await message.answer(build_status_text(settings))

    @dp.message(F.text | F.caption)
    async def handle_message(message: Message, bot: Bot) -> None:
        if settings.forwarded_mode == "copy":
            await bot.copy_message(
                chat_id=settings.target_chat_id,
                from_chat_id=message.chat.id,
                message_id=message.message_id,
            )
            await message.reply("Скопировал сообщение в канал.")
            return

        text = message.text or message.caption or ""
        if not looks_like_vacancy_message(text):
            await message.reply("I skipped this message because it does not look like an IT vacancy.")
            return

        vacancy = parse_message_to_vacancy(text)
        if not vacancy.url:
            origin_url = forwarded_public_post_url(message)
            if origin_url:
                vacancy = replace(vacancy, source="Telegram", url=origin_url)
        if store.seen(vacancy):
            await message.reply("Похоже, эта вакансия уже публиковалась.")
            return

        card = format_vacancy_card(vacancy)
        await bot.send_message(
            chat_id=settings.target_chat_id,
            text=card,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
        store.mark_published(vacancy)
        await message.reply("Опубликовал вакансию в канал.")

    return dp


async def run_bot(settings: Settings) -> None:
    settings.require_runtime()
    logging.basicConfig(level=logging.INFO)

    store = VacancyStore(settings.database_path)
    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = create_dispatcher(settings, store)
    polling_task = asyncio.create_task(poll_sources_forever(bot, settings, store))

    try:
        await dp.start_polling(bot)
    finally:
        polling_task.cancel()
        try:
            await polling_task
        except asyncio.CancelledError:
            pass
        await bot.session.close()


def run_bot_sync(settings: Settings) -> None:
    asyncio.run(run_bot(settings))
