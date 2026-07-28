from __future__ import annotations

from dataclasses import dataclass

from aiogram import Bot
from aiogram.exceptions import TelegramNetworkError

from .config import Settings
from .storage import VacancyStore

DIAGNOSTIC_TELEGRAM_REQUEST_TIMEOUT_SECONDS = 15


@dataclass(frozen=True)
class ApplicationQueueDiagnostics:
    bot_id: int | None
    bot_username: str | None
    target_title: str | None
    target_type: str | None
    webhook_configured: bool | None
    pending_update_count: int | None
    published_vacancies: int
    applications: int
    queue_resume_registered: bool
    telegram_error: str | None = None


def format_application_queue_diagnostics(result: ApplicationQueueDiagnostics) -> str:
    lines = ["Application queue diagnostics"]
    if result.telegram_error:
        lines.append(f"Telegram API: unavailable ({result.telegram_error})")
        lines.append("Bot: unknown")
        lines.append("Target: unknown")
        lines.append("Webhook configured: unknown")
        lines.append("Pending Telegram updates: unknown")
    else:
        lines.extend(
            [
                f"Bot: @{result.bot_username} (id={result.bot_id})",
                f"Target: {result.target_title} ({result.target_type})",
                f"Webhook configured: {'yes' if result.webhook_configured else 'no'}",
                f"Pending Telegram updates: {result.pending_update_count}",
            ]
        )
    lines.extend(
        [
            f"Published vacancies in SQLite: {result.published_vacancies}",
            f"Applications in SQLite: {result.applications}",
            f"Queue resume registered: {'yes' if result.queue_resume_registered else 'no'}",
        ]
    )
    return "\n".join(lines)


async def collect_application_queue_diagnostics(
    settings: Settings,
    *,
    bot: Bot | None = None,
    store: VacancyStore | None = None,
) -> ApplicationQueueDiagnostics:
    """Inspect queue state without consuming or acknowledging Telegram updates."""
    settings.require_application_queue()
    owned_bot = bot is None
    bot = bot or Bot(token=settings.telegram_bot_token)
    store = store or VacancyStore(settings.database_path)
    operator_user_id = settings.operator_user_ids[0]
    profile = store.get_operator_profile(operator_user_id)
    published_vacancies, applications = store.application_queue_counts()
    queue_resume_registered = bool(
        (profile and profile.resume_telegram_file_id)
        or settings.application_queue_resume_file_id.strip()
    )
    try:
        me = await bot.get_me(request_timeout=DIAGNOSTIC_TELEGRAM_REQUEST_TIMEOUT_SECONDS)
        chat = await bot.get_chat(
            settings.target_chat_id,
            request_timeout=DIAGNOSTIC_TELEGRAM_REQUEST_TIMEOUT_SECONDS,
        )
        webhook = await bot.get_webhook_info(
            request_timeout=DIAGNOSTIC_TELEGRAM_REQUEST_TIMEOUT_SECONDS
        )
        return ApplicationQueueDiagnostics(
            bot_id=me.id,
            bot_username=me.username or str(me.id),
            target_title=chat.title or chat.full_name or str(chat.id),
            target_type=str(chat.type),
            webhook_configured=bool(webhook.url),
            pending_update_count=webhook.pending_update_count,
            published_vacancies=published_vacancies,
            applications=applications,
            queue_resume_registered=queue_resume_registered,
        )
    except (TelegramNetworkError, TimeoutError) as exc:
        return ApplicationQueueDiagnostics(
            bot_id=None,
            bot_username=None,
            target_title=None,
            target_type=None,
            webhook_configured=None,
            pending_update_count=None,
            published_vacancies=published_vacancies,
            applications=applications,
            queue_resume_registered=queue_resume_registered,
            telegram_error=_safe_telegram_error(exc),
        )
    finally:
        if owned_bot:
            await bot.session.close()


def _safe_telegram_error(exc: BaseException) -> str:
    if isinstance(exc, TelegramNetworkError):
        return "TelegramNetworkError: " + str(exc)
    return type(exc).__name__
