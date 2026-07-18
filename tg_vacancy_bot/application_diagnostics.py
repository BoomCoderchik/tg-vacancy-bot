from __future__ import annotations

from dataclasses import dataclass

from aiogram import Bot

from .config import Settings
from .storage import VacancyStore


@dataclass(frozen=True)
class ApplicationQueueDiagnostics:
    bot_id: int
    bot_username: str
    target_title: str
    target_type: str
    webhook_configured: bool
    pending_update_count: int
    published_vacancies: int
    applications: int
    queue_resume_registered: bool


def format_application_queue_diagnostics(result: ApplicationQueueDiagnostics) -> str:
    return "\n".join(
        [
            "Application queue diagnostics",
            f"Bot: @{result.bot_username} (id={result.bot_id})",
            f"Target: {result.target_title} ({result.target_type})",
            f"Webhook configured: {'yes' if result.webhook_configured else 'no'}",
            f"Pending Telegram updates: {result.pending_update_count}",
            f"Published vacancies in SQLite: {result.published_vacancies}",
            f"Applications in SQLite: {result.applications}",
            f"Queue resume registered: {'yes' if result.queue_resume_registered else 'no'}",
        ]
    )


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
    try:
        me = await bot.get_me()
        chat = await bot.get_chat(settings.target_chat_id)
        webhook = await bot.get_webhook_info()
        profile = store.get_operator_profile(operator_user_id)
        published_vacancies, applications = store.application_queue_counts()
        return ApplicationQueueDiagnostics(
            bot_id=me.id,
            bot_username=me.username or str(me.id),
            target_title=chat.title or chat.full_name or str(chat.id),
            target_type=str(chat.type),
            webhook_configured=bool(webhook.url),
            pending_update_count=webhook.pending_update_count,
            published_vacancies=published_vacancies,
            applications=applications,
            queue_resume_registered=bool(
                (profile and profile.resume_telegram_file_id)
                or settings.application_queue_resume_file_id.strip()
            ),
        )
    finally:
        if owned_bot:
            await bot.session.close()
