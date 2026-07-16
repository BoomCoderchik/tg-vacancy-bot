from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from aiogram import Bot
from aiogram.methods import GetUpdates
from aiogram.types import CallbackQuery, Update

from .application_buttons import APPLICATION_CALLBACK_PREFIX
from .bot import send_application_result_notification
from .browser_worker import BrowserWorker
from .config import Settings
from .models import OperatorProfile
from .storage import VacancyStore


logger = logging.getLogger(__name__)
RETRYABLE_PRE_SUBMIT_STATUSES = frozenset({"created", "queued", "loading"})


@dataclass(frozen=True)
class ApplicationQueueResult:
    enabled: bool
    updates_seen: int = 0
    applications_processed: int = 0
    submitted: int = 0
    manual_required: int = 0
    failed: int = 0
    skipped: int = 0


def format_application_queue_result(result: ApplicationQueueResult) -> str:
    if not result.enabled:
        return "Application queue is disabled."
    return (
        "Application queue: "
        f"updates={result.updates_seen} processed={result.applications_processed} "
        f"submitted={result.submitted} manual={result.manual_required} "
        f"failed={result.failed} skipped={result.skipped}"
    )


def queue_operator_profile(settings: Settings, operator_user_id: int) -> OperatorProfile:
    extra_fields = {}
    if settings.application_queue_profile_personal_url.strip():
        extra_fields["personal_url"] = settings.application_queue_profile_personal_url.strip()
    if settings.application_queue_profile_cover_letter.strip():
        extra_fields["cover_letter"] = settings.application_queue_profile_cover_letter.strip()
    return OperatorProfile(
        operator_user_id=operator_user_id,
        full_name=settings.application_queue_profile_full_name.strip(),
        email=settings.application_queue_profile_email.strip(),
        phone=settings.application_queue_profile_phone.strip() or None,
        extra_fields=extra_fields,
        resume_original_name=settings.application_queue_resume_file_name,
        resume_telegram_file_id=settings.application_queue_resume_file_id.strip(),
    )


async def process_application_queue_once(
    settings: Settings,
    *,
    bot: Bot | None = None,
    store: VacancyStore | None = None,
    browser_worker: BrowserWorker | None = None,
) -> ApplicationQueueResult:
    if not settings.application_queue_enabled:
        return ApplicationQueueResult(enabled=False)
    settings.require_application_queue()
    logging.basicConfig(level=logging.INFO)

    owned_bot = bot is None
    bot = bot or Bot(token=settings.telegram_bot_token)
    store = store or VacancyStore(settings.database_path)
    result = ApplicationQueueResult(enabled=True)
    offset: int | None = None
    try:
        while True:
            updates: list[Update] = await bot(
                GetUpdates(
                    offset=offset,
                    limit=100,
                    timeout=0,
                    allowed_updates=["callback_query"],
                )
            )
            if not updates:
                return result
            for update in updates:
                result = await _process_update(update, settings, bot, store, browser_worker, result)
            offset = updates[-1].update_id + 1
    finally:
        if owned_bot:
            await bot.session.close()


async def _process_update(
    update: Update,
    settings: Settings,
    bot: Bot,
    store: VacancyStore,
    browser_worker: BrowserWorker | None,
    result: ApplicationQueueResult,
) -> ApplicationQueueResult:
    values = result.__dict__ | {"updates_seen": result.updates_seen + 1}
    callback = update.callback_query
    if callback is None or not (callback.data or "").startswith(APPLICATION_CALLBACK_PREFIX):
        values["skipped"] += 1
        return ApplicationQueueResult(**values)

    operator_user_id = callback.from_user.id
    if operator_user_id not in settings.operator_user_ids:
        await _answer_callback_quietly(bot, callback, "Отклик доступен только оператору.")
        values["skipped"] += 1
        return ApplicationQueueResult(**values)

    await _answer_callback_quietly(bot, callback, "Отклик принят в обработку.")
    vacancy_id = (callback.data or "").removeprefix(APPLICATION_CALLBACK_PREFIX)
    application_result = store.create_application(operator_user_id, vacancy_id)
    if application_result is None:
        await bot.send_message(
            chat_id=operator_user_id,
            text="⚠️ Вакансия больше не найдена в очереди GitHub Actions. Отклик не отправлен.",
        )
        values["failed"] += 1
        return ApplicationQueueResult(**values)

    application, created = application_result
    if not created and application.status == "submitting":
        store.update_application_status(
            application.application_id,
            "manual_required",
            "A previous runner stopped during submission. Automatic retry is disabled to prevent a duplicate.",
        )
        await send_application_result_notification(bot, operator_user_id, "manual_required", application.vacancy_url)
        values["manual_required"] += 1
        return ApplicationQueueResult(**values)
    if not created and application.status not in RETRYABLE_PRE_SUBMIT_STATUSES:
        await send_application_result_notification(bot, operator_user_id, application.status, application.vacancy_url)
        values["skipped"] += 1
        return ApplicationQueueResult(**values)

    values["applications_processed"] += 1
    store.update_application_status(application.application_id, "queued")
    submit_started = False
    try:
        with TemporaryDirectory(prefix="tg-vacancy-application-") as temporary_dir:
            temporary_path = Path(temporary_dir)
            resume_path = temporary_path / settings.application_queue_resume_file_name
            await _download_resume(bot, settings, resume_path)
            store.update_application_status(application.application_id, "loading")
            profile = queue_operator_profile(settings, operator_user_id)
            worker = browser_worker or BrowserWorker(
                str(temporary_path / "browser-profile"),
                settings.application_allowed_domains,
                True,
                settings.browser_timeout_seconds,
            )

            def before_submit() -> None:
                nonlocal submit_started
                submit_started = True
                store.update_application_status(application.application_id, "submitting")

            inspection = await worker.submit_application(
                application.vacancy_url or "",
                profile,
                resume_path,
                before_submit=before_submit,
            )
        store.update_application_status(application.application_id, inspection.status, inspection.error)
        await send_application_result_notification(
            bot,
            operator_user_id,
            inspection.status,
            application.vacancy_url,
            missing_fields=inspection.missing_fields,
        )
        if inspection.status == "submitted":
            values["submitted"] += 1
        elif inspection.status == "manual_required":
            values["manual_required"] += 1
        else:
            values["failed"] += 1
        return ApplicationQueueResult(**values)
    except Exception:
        logger.exception("Queued application processing failed for application_id=%s", application.application_id)
        status = "manual_required" if submit_started else "failed"
        error = (
            "The runner stopped after submission started. Automatic retry is disabled to prevent a duplicate."
            if submit_started
            else "Queued application processing failed before submission."
        )
        store.update_application_status(application.application_id, status, error)
        await send_application_result_notification(bot, operator_user_id, status, application.vacancy_url)
        values["manual_required" if submit_started else "failed"] += 1
        return ApplicationQueueResult(**values)


async def _download_resume(bot: Bot, settings: Settings, destination: Path) -> None:
    telegram_file = await bot.get_file(settings.application_queue_resume_file_id.strip())
    if telegram_file.file_size and telegram_file.file_size > settings.resume_max_size_bytes:
        raise RuntimeError("Telegram resume exceeds RESUME_MAX_SIZE_BYTES.")
    if not telegram_file.file_path:
        raise RuntimeError("Telegram did not return a resume file path.")
    await bot.download_file(telegram_file.file_path, destination=destination)
    if not destination.is_file() or destination.stat().st_size == 0:
        raise RuntimeError("Telegram resume download produced an empty file.")


async def _answer_callback_quietly(bot: Bot, callback: CallbackQuery, text: str) -> None:
    try:
        await bot.answer_callback_query(callback.id, text=text)
    except Exception:
        logger.info("Callback query is too old to acknowledge; processing continues.")
