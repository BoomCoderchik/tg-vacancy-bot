from __future__ import annotations

import asyncio
import logging
from dataclasses import replace

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message

from .access_control import is_authorized_user
from .config import Settings
from .description_localization import localize_vacancy_description
from .formatting import format_vacancy_card
from .intake import looks_like_vacancy_message
from .preview import parse_publishable_message
from .runtime_lock import SingleInstanceLock, bot_run_lock_path
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
        f"LinkedInPosts={_linkedin_post_search_state(settings)}",
        f"LinkedInPostScraper={'on' if settings.enable_linkedin_post_scraper else 'off'}",
        f"JobSpyLinkedIn={'on' if settings.enable_jobspy_linkedin else 'off'}",
        f"Adzuna={'on' if settings.adzuna_app_id and settings.adzuna_app_key else 'off'}",
        f"Jooble={'on' if settings.jooble_api_key else 'off'}",
    ]
    return "\n".join(
        [
            "TG Vacancy Bot status",
            f"Forwarded mode: {settings.forwarded_mode}",
        f"Target chat: {settings.target_chat_id or 'not configured'}",
        f"Operator allowlist: {'on' if settings.operator_user_ids else 'off'}",
        f"Description localization: {'on' if settings.localize_descriptions else 'off'}",
        f"Source polling interval: {settings.source_poll_interval_seconds}s",
            "Sources: " + ", ".join(source_states),
        ]
    )


def _linkedin_post_search_state(settings: Settings) -> str:
    if not settings.enable_linkedin_post_search:
        return "off"
    if not settings.serpapi_api_key:
        return "missing-key"
    return "on"


def format_whoami_text(user_id: int | None) -> str:
    if user_id is None:
        return "Telegram user ID is not available for this message."
    return f"Your Telegram user ID: {user_id}"


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
        if not _message_is_authorized(message, settings):
            await message.reply("Not authorized.")
            return
        await message.answer(build_status_text(settings))

    @dp.message(Command("whoami"))
    async def whoami(message: Message) -> None:
        user_id = message.from_user.id if message.from_user else None
        await message.answer(format_whoami_text(user_id))

    @dp.message(F.text | F.caption)
    async def handle_message(message: Message, bot: Bot) -> None:
        if not _message_is_authorized(message, settings):
            await message.reply("Not authorized.")
            return

        text = message.text or message.caption or ""
        if not looks_like_vacancy_message(text):
            await message.reply("I skipped this message because it does not look like an allowed development vacancy.")
            return

        if settings.forwarded_mode == "copy":
            await bot.copy_message(
                chat_id=settings.target_chat_id,
                from_chat_id=message.chat.id,
                message_id=message.message_id,
            )
            await message.reply("Скопировал сообщение в канал.")
            return

        vacancy = parse_publishable_message(text)
        if not vacancy.url:
            origin_url = forwarded_public_post_url(message)
            if origin_url:
                vacancy = replace(vacancy, source="Telegram", url=origin_url)
        if store.seen(vacancy):
            await message.reply("Похоже, эта вакансия уже публиковалась.")
            return

        try:
            public_vacancy = await localize_vacancy_description(vacancy, settings)
        except RuntimeError as exc:
            logger.exception("Description localization failed")
            await message.reply(f"Не смог подготовить русское описание: {exc}")
            return

        card = format_vacancy_card(public_vacancy)
        await bot.send_message(
            chat_id=settings.target_chat_id,
            text=card,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
        )
        store.mark_published(vacancy)
        await message.reply("Опубликовал вакансию в канал.")

    return dp


def _message_is_authorized(message: Message, settings: Settings) -> bool:
    user_id = message.from_user.id if message.from_user else None
    return is_authorized_user(user_id, settings.operator_user_ids)


async def run_bot(settings: Settings) -> None:
    settings.require_runtime()
    logging.basicConfig(level=logging.INFO)

    lock_path = bot_run_lock_path(settings.database_path, settings.telegram_bot_token)
    with SingleInstanceLock(lock_path):
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
