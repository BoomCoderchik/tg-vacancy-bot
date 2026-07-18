from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from pathlib import Path
from tempfile import TemporaryDirectory

from aiogram import Bot
from aiogram.methods import GetUpdates
from aiogram.types import CallbackQuery, Message, Update

from .application_buttons import APPLICATION_CALLBACK_PREFIX
from .bot import send_application_prepared_notification, send_application_result_notification
from .browser_worker import BrowserWorker
from .config import Settings
from .models import OperatorProfile
from .storage import VacancyStore


logger = logging.getLogger(__name__)
RETRYABLE_PRE_SUBMIT_STATUSES = frozenset({"created", "queued", "loading", "profile_missing"})
RETRYABLE_PRE_SUBMIT_MANUAL_ERRORS = frozenset(
    {"Arbeitnow redirected the application to an unsupported external site."}
)
QUEUE_RESUME_COMMAND = "/queue_resume"
ALLOWED_RESUME_SUFFIXES = frozenset({".pdf", ".docx"})


@dataclass(frozen=True)
class ApplicationQueueResult:
    enabled: bool
    updates_seen: int = 0
    applications_processed: int = 0
    submitted: int = 0
    manual_required: int = 0
    failed: int = 0
    skipped: int = 0
    resumes_updated: int = 0


def format_application_queue_result(result: ApplicationQueueResult) -> str:
    if not result.enabled:
        return "Application queue is disabled."
    return (
        "Application queue: "
        f"updates={result.updates_seen} processed={result.applications_processed} "
        f"submitted={result.submitted} manual={result.manual_required} "
        f"failed={result.failed} skipped={result.skipped}"
        f" resumes_updated={result.resumes_updated}"
    )


def queue_operator_profile(
    settings: Settings,
    operator_user_id: int,
    stored_profile: OperatorProfile | None = None,
) -> OperatorProfile:
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
        resume_original_name=(
            stored_profile.resume_original_name
            if stored_profile and stored_profile.resume_telegram_file_id
            else settings.application_queue_resume_file_name
        ),
        resume_telegram_file_id=(
            stored_profile.resume_telegram_file_id
            if stored_profile and stored_profile.resume_telegram_file_id
            else settings.application_queue_resume_file_id.strip() or None
        ),
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
                    allowed_updates=["callback_query", "message"],
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
    message = update.message
    if message is not None and _is_queue_resume_command(message):
        return await _save_queued_resume(message, settings, bot, store, values)

    callback = update.callback_query
    if callback is None or not (callback.data or "").startswith(APPLICATION_CALLBACK_PREFIX):
        values["skipped"] += 1
        return ApplicationQueueResult(**values)

    operator_user_id = callback.from_user.id
    if operator_user_id not in settings.operator_user_ids:
        await _answer_callback_quietly(bot, callback, "Отклик доступен только оператору.")
        values["skipped"] += 1
        return ApplicationQueueResult(**values)

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
    if application.status == "failed":
        await _answer_callback_quietly(bot, callback, "Отклик не отправлен: у вакансии нет ссылки.")
        await send_application_result_notification(
            bot,
            operator_user_id,
            application.status,
            application.vacancy_url,
            error_description=application.error_description,
        )
        values["failed"] += 1
        return ApplicationQueueResult(**values)
    if not created and application.status == "submitting":
        error = "A previous runner stopped during submission. Automatic retry is disabled to prevent a duplicate."
        store.update_application_status(
            application.application_id,
            "manual_required",
            error,
        )
        await send_application_result_notification(
            bot,
            operator_user_id,
            "manual_required",
            application.vacancy_url,
            error_description=error,
        )
        values["manual_required"] += 1
        return ApplicationQueueResult(**values)
    retryable_manual_result = (
        application.status == "manual_required"
        and application.error_description in RETRYABLE_PRE_SUBMIT_MANUAL_ERRORS
    )
    if (
        not created
        and application.status not in RETRYABLE_PRE_SUBMIT_STATUSES
        and not retryable_manual_result
    ):
        await send_application_result_notification(
            bot,
            operator_user_id,
            application.status,
            application.vacancy_url,
            error_description=application.error_description,
        )
        values["skipped"] += 1
        return ApplicationQueueResult(**values)

    values["applications_processed"] += 1
    store.update_application_status(application.application_id, "queued")
    await _answer_callback_quietly(bot, callback, "Отклик подготовлен.")
    await send_application_prepared_notification(bot, operator_user_id, application.vacancy_url)
    profile = queue_operator_profile(settings, operator_user_id, store.get_operator_profile(operator_user_id))
    if not profile.resume_telegram_file_id or not profile.resume_original_name:
        store.update_application_status(
            application.application_id,
            "profile_missing",
            "Queue resume is not configured.",
        )
        await bot.send_message(
            chat_id=operator_user_id,
            text=(
                "Резюме для очереди ещё не сохранено. Отправьте этому боту PDF или DOCX "
                "с подписью /queue_resume, дождитесь подтверждения и нажмите кнопку отклика снова."
            ),
        )
        values["failed"] += 1
        return ApplicationQueueResult(**values)
    submit_started = False
    try:
        with TemporaryDirectory(prefix="tg-vacancy-application-") as temporary_dir:
            temporary_path = Path(temporary_dir)
            resume_path = temporary_path / profile.resume_original_name
            await _download_resume(
                bot,
                profile.resume_telegram_file_id,
                resume_path,
                settings.resume_max_size_bytes,
            )
            store.update_application_status(application.application_id, "loading")
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
        logger.info(
            "Queued application result application_id=%s status=%s error=%s",
            application.application_id,
            inspection.status,
            inspection.error or "",
        )
        store.update_application_status(application.application_id, inspection.status, inspection.error)
        await send_application_result_notification(
            bot,
            operator_user_id,
            inspection.status,
            application.vacancy_url,
            missing_fields=inspection.missing_fields,
            error_description=inspection.error,
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
        await send_application_result_notification(
            bot,
            operator_user_id,
            status,
            application.vacancy_url,
            error_description=error,
        )
        values["manual_required" if submit_started else "failed"] += 1
        return ApplicationQueueResult(**values)


def _is_queue_resume_command(message: Message) -> bool:
    content = (message.caption or message.text or "").strip()
    if not content:
        return False
    command_text = content.split(maxsplit=1)[0].lower()
    return command_text.split("@", maxsplit=1)[0] == QUEUE_RESUME_COMMAND


async def _save_queued_resume(
    message: Message,
    settings: Settings,
    bot: Bot,
    store: VacancyStore,
    values: dict,
) -> ApplicationQueueResult:
    operator_user_id = message.from_user.id if message.from_user else None
    if operator_user_id not in settings.operator_user_ids:
        values["skipped"] += 1
        return ApplicationQueueResult(**values)
    if message.chat.type != "private":
        await bot.send_message(
            chat_id=operator_user_id,
            text="Резюме для очереди можно обновлять только в личном чате с ботом.",
        )
        values["skipped"] += 1
        return ApplicationQueueResult(**values)
    document = message.document
    if document is None or not document.file_name:
        await bot.send_message(
            chat_id=operator_user_id,
            text="Отправьте PDF или DOCX как документ с подписью /queue_resume.",
        )
        values["skipped"] += 1
        return ApplicationQueueResult(**values)
    file_name = Path(document.file_name).name
    if file_name != document.file_name or Path(file_name).suffix.lower() not in ALLOWED_RESUME_SUFFIXES:
        await bot.send_message(
            chat_id=operator_user_id,
            text="Для очереди принимаются только файлы PDF или DOCX с безопасным именем.",
        )
        values["skipped"] += 1
        return ApplicationQueueResult(**values)
    if document.file_size and document.file_size > settings.resume_max_size_bytes:
        await bot.send_message(
            chat_id=operator_user_id,
            text=f"Файл слишком большой. Максимум: {settings.resume_max_size_bytes // (1024 * 1024)} МБ.",
        )
        values["skipped"] += 1
        return ApplicationQueueResult(**values)

    stored_profile = store.get_operator_profile(operator_user_id) or OperatorProfile(
        operator_user_id=operator_user_id
    )
    store.save_operator_profile(
        replace(
            stored_profile,
            resume_original_name=file_name,
            resume_telegram_file_id=document.file_id,
        )
    )
    await bot.send_message(
        chat_id=operator_user_id,
        text=(
            f"Резюме «{file_name}» сохранено для очереди откликов. "
            "GitHub secret с file_id больше не требуется."
        ),
    )
    values["resumes_updated"] += 1
    return ApplicationQueueResult(**values)


async def _download_resume(
    bot: Bot,
    file_id: str,
    destination: Path,
    max_size_bytes: int,
) -> None:
    telegram_file = await bot.get_file(file_id)
    if telegram_file.file_size and telegram_file.file_size > max_size_bytes:
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
