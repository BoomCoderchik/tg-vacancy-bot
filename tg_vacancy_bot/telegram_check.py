from __future__ import annotations

from dataclasses import dataclass

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ChatMemberStatus, ParseMode
from aiogram.exceptions import TelegramAPIError

from .config import Settings


@dataclass(frozen=True)
class TelegramCheckResult:
    bot_username: str
    target_title: str
    target_type: str
    membership_status: str
    can_post_messages: bool


def format_check_result(result: TelegramCheckResult) -> str:
    post_status = "yes" if result.can_post_messages else "unknown/no"
    return "\n".join(
        [
            "Telegram check OK",
            f"Bot: @{result.bot_username}",
            f"Target: {result.target_title} ({result.target_type})",
            f"Bot membership: {result.membership_status}",
            f"Can post messages: {post_status}",
        ]
    )


async def check_telegram_access(settings: Settings) -> TelegramCheckResult:
    settings.require_runtime()
    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    try:
        me = await bot.get_me()
        chat = await bot.get_chat(settings.target_chat_id)
        member = await bot.get_chat_member(chat.id, me.id)
        status = getattr(member, "status", "unknown")
        return TelegramCheckResult(
            bot_username=me.username or str(me.id),
            target_title=chat.title or chat.full_name or str(chat.id),
            target_type=str(chat.type),
            membership_status=str(status),
            can_post_messages=_can_post_messages(member),
        )
    except TelegramAPIError as exc:
        raise RuntimeError(f"Telegram API check failed: {exc.message}") from exc
    finally:
        await bot.session.close()


def _can_post_messages(member: object) -> bool:
    status = getattr(member, "status", None)
    if status == ChatMemberStatus.CREATOR:
        return True
    if status == ChatMemberStatus.ADMINISTRATOR:
        return bool(getattr(member, "can_post_messages", True))
    return False
