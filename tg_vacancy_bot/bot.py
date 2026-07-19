from __future__ import annotations

import asyncio
from html import escape
from io import BytesIO
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ChatType, ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from .access_control import is_authorized_user
from .application_buttons import APPLICATION_CALLBACK_PREFIX, application_button
from .browser_worker import BrowserWorker
from .config import Settings
from .description_localization import localize_vacancy_description
from .formatting import format_vacancy_card
from .intake import looks_like_vacancy_message
from .preview import parse_publishable_message
from .runtime_lock import SingleInstanceLock, bot_run_lock_path
from .models import ApplicationStatus, OperatorProfile
from .profile_flow import (
    CANCEL_TEXT,
    DONE_TEXT,
    PROFILE_FIELDS,
    SKIP_TEXT,
    clean_profile_value,
    format_profile_summary,
    is_profile_operator,
    parse_extra_field,
    profile_with_extra_field,
    profile_with_field,
)
from .resume_storage import ResumeStorage
from .profile_service import ProfileService
from .source_polling import poll_sources_forever
from .storage import VacancyStore
from .telegram_origin import forwarded_public_post_url

logger = logging.getLogger(__name__)


class ProfileForm(StatesGroup):
    full_name = State()
    email = State()
    phone = State()
    desired_salary = State()
    location = State()
    work_format = State()
    employment_type = State()
    extra_fields = State()
    resume = State()


def build_status_text(settings: Settings) -> str:
    source_states = [
        f"Arbeitnow={'on' if settings.enable_arbeitnow else 'off'}",
        f"WorkingNomads={'on' if settings.enable_working_nomads else 'off'}",
        f"LinkedInPosts={_linkedin_post_search_state(settings)}",
        f"LinkedInPostScraper={_linkedin_post_scraper_state(settings)}",
        f"LinkedInHeadless={_linkedin_headless_state(settings)}",
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
    if settings.enable_linkedin_post_headless:
        return "suppressed-by-headless"
    if not (settings.serpapi_api_key or settings.serper_api_key):
        return "missing-key"
    return "on"


def _linkedin_post_scraper_state(settings: Settings) -> str:
    if not settings.enable_linkedin_post_scraper:
        return "off"
    if settings.enable_linkedin_post_headless:
        return "suppressed-by-headless"
    return "on"


def _linkedin_headless_state(settings: Settings) -> str:
    if not settings.enable_linkedin_post_headless:
        return "off"
    if not settings.linkedin_headless_access_authorized:
        return "permission-required"
    if not settings.linkedin_headless_permission_reference.strip():
        return "permission-reference-required"
    return "on"


def format_whoami_text(user_id: int | None) -> str:
    if user_id is None:
        return "Telegram user ID is not available for this message."
    return f"Your Telegram user ID: {user_id}"


def queue_resume_id_text(profile: OperatorProfile | None) -> str:
    if not profile or not profile.resume_telegram_file_id:
        return "Сначала загрузите резюме через /profile при запущенном локальном боте."
    return (
        "Скопируйте значение в GitHub secret APPLICATION_QUEUE_RESUME_FILE_ID:\n\n"
        f"<code>{escape(profile.resume_telegram_file_id)}</code>"
    )


def manual_application_link_text(vacancy_url: str) -> str:
    return (
        "Автозаполнение для этой формы пока не поддерживается. "
        f'<a href="{escape(vacancy_url, quote=True)}">Открыть вакансию и откликнуться вручную</a>.'
    )


def application_result_text(
    status: ApplicationStatus,
    *,
    missing_fields: tuple[str, ...] = (),
    error_description: str | None = None,
) -> str:
    """Describe the real application state without implying a submission that did not happen."""
    if status == "submitted":
        return "✅ Отклик отправлен."
    if status == "filled":
        return (
            "🟡 Отклик ещё не отправлен.\n\n"
            "Форма заполнена, но финальная отправка не выполнялась. "
            "Откройте вакансию и подтвердите отправку вручную."
        )
    if status == "profile_missing":
        missing = ", ".join(missing_fields) or "обязательные данные"
        return (
            "❌ Отклик не отправлен.\n\n"
            f"Не хватает данных профиля: {missing}. Заполните их через /profile и попробуйте снова."
        )
    if status in {"manual_required", "unsupported_site"}:
        text = (
            "⚠️ Отклик не отправлен автоматически.\n\n"
            "Для этой вакансии требуется открыть форму и завершить отклик вручную."
        )
        if detail := _application_error_detail(error_description):
            text += f"\n\nПричина: {detail}"
        return text
    if status == "awaiting_confirmation":
        return (
            "🟡 Отклик ещё не отправлен.\n\n"
            "Форма ожидает вашего подтверждения перед отправкой."
        )
    if status == "failed":
        text = "❌ Не удалось отправить отклик. Попробуйте ещё раз или откройте вакансию вручную."
        if detail := _application_error_detail(error_description):
            text += f"\n\nПричина: {detail}"
        return text
    if status == "cancelled":
        return "Отклик отменён и не отправлен."
    return "⏳ Отклик обрабатывается. Бот сообщит результат отдельным сообщением."


def _application_error_detail(error_description: str | None) -> str | None:
    """Return a safe user-facing reason without exposing raw runner details."""
    if not error_description:
        return None
    normalized = " ".join(error_description.strip().split()).lower()
    known_reasons = (
        (
            "vacancy does not contain an external application url",
            "у вакансии нет внешней ссылки на форму отклика.",
        ),
        (
            "domain is not in application_allowed_domains",
            "домен формы не включён в список разрешённых для автоотклика.",
        ),
        (
            "no application adapter is registered for this site",
            "для этого сайта ещё нет поддерживаемого автозаполнения.",
        ),
        (
            "arbeitnow redirected the application to an unsupported external site",
            "Arbeitnow открыл внешнюю форму, которую бот пока не заполняет автоматически.",
        ),
        (
            "arbeitnow application form has changed",
            "разметка формы Arbeitnow отличается от ожидаемой.",
        ),
        (
            "arbeitnow application form is ambiguous",
            "на странице найдено несколько вариантов формы, и бот не может безопасно выбрать один.",
        ),
        (
            "arbeitnow submit control has changed",
            "кнопка отправки отличается от ожидаемой или недоступна.",
        ),
        (
            "success state could not be verified",
            "бот заполнил форму, но не смог надёжно подтвердить успешную отправку; повторять автоматически небезопасно.",
        ),
        (
            "site protection detected",
            "на странице обнаружена защита вроде CAPTCHA или 2FA.",
        ),
        (
            "login is required",
            "форма требует входа в аккаунт.",
        ),
        (
            "previous runner stopped during submission",
            "предыдущий запуск остановился во время отправки; автоматический повтор отключён, чтобы не отправить дубль.",
        ),
        (
            "runner stopped after submission started",
            "запуск остановился после начала отправки; автоматический повтор отключён, чтобы не отправить дубль.",
        ),
        (
            "queued application processing failed before submission",
            "очередь остановилась до начала отправки, поэтому можно попробовать ещё раз.",
        ),
        (
            "browser preparation failed",
            "браузерный запуск не смог подготовить форму.",
        ),
        (
            "browser inspection failed",
            "браузерный запуск не смог проверить страницу.",
        ),
    )
    for marker, reason in known_reasons:
        if marker in normalized:
            return reason
    return "бот остановил автоматическую отправку из-за неподдержанного состояния формы."


def application_prepared_text() -> str:
    return (
        "Отклик подготовлен.\n\n"
        "Я сохранил заявку по этой вакансии. Бот попробует обработать её через поддерживаемую форму "
        "и пришлёт фактический результат отдельным сообщением."
    )


def application_result_markup(vacancy_url: str | None) -> InlineKeyboardMarkup | None:
    if not vacancy_url:
        return None
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Открыть вакансию", url=vacancy_url)]]
    )


async def send_application_prepared_notification(
    bot: Bot,
    operator_user_id: int,
    vacancy_url: str | None,
) -> bool:
    """Send a durable private queue confirmation; return False when Telegram rejects the DM."""
    try:
        await bot.send_message(
            chat_id=operator_user_id,
            text=application_prepared_text(),
            reply_markup=application_result_markup(vacancy_url),
        )
    except Exception:
        logger.warning("Could not send private application prepared notification.")
        return False
    return True


async def send_application_result_notification(
    bot: Bot,
    operator_user_id: int,
    status: ApplicationStatus,
    vacancy_url: str | None,
    *,
    missing_fields: tuple[str, ...] = (),
    error_description: str | None = None,
) -> bool:
    """Send a durable private result message; return False when Telegram rejects the DM."""
    try:
        await bot.send_message(
            chat_id=operator_user_id,
            text=application_result_text(
                status,
                missing_fields=missing_fields,
                error_description=error_description,
            ),
            reply_markup=application_result_markup(vacancy_url),
        )
    except Exception:
        logger.warning("Could not send private application result notification.")
        return False
    return True


def profile_onboarding_missing_fields(profile: OperatorProfile | None) -> tuple[str, ...]:
    """Return the private data required by the currently supported application adapter."""
    missing: list[str] = []
    name_parts = (profile.full_name or "").strip().split() if profile else []
    if len(name_parts) < 2:
        missing.append("имя и фамилия")
    if not profile or not profile.email:
        missing.append("email")
    if not profile or not profile.resume_stored_name:
        missing.append("резюме в PDF или DOCX")
    return tuple(missing)


def profile_onboarding_text(profile: OperatorProfile | None) -> str:
    missing = ", ".join(profile_onboarding_missing_fields(profile))
    return (
        "Чтобы подготовить отклики, загрузите резюме и заполните профиль.\n"
        f"Сейчас нужны: {missing}.\n\n"
        "Нажмите «Заполнить поля», затем «Загрузить резюме». "
        "Без этих данных бот не будет пытаться заполнить форму вакансии."
    )


def needs_profile_onboarding(profile: OperatorProfile | None) -> bool:
    return bool(profile_onboarding_missing_fields(profile))


def profile_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Заполнить поля", callback_data="profile:edit")],
            [InlineKeyboardButton(text="Загрузить резюме", callback_data="profile:resume")],
            [InlineKeyboardButton(text="Удалить профиль", callback_data="profile:delete")],
        ]
    )


def profile_confirm_delete_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Удалить", callback_data="profile:delete:confirm")],
            [InlineKeyboardButton(text="Отмена", callback_data="profile:delete:cancel")],
        ]
    )


async def send_profile_onboarding_reminders(bot: Bot, settings: Settings, store: VacancyStore) -> None:
    """Prompt known operators after a bot restart until their application profile is ready."""
    for operator_user_id in settings.operator_user_ids:
        profile = store.get_operator_profile(operator_user_id)
        if not needs_profile_onboarding(profile):
            continue
        try:
            await bot.send_message(
                chat_id=operator_user_id,
                text=profile_onboarding_text(profile),
                reply_markup=profile_menu(),
            )
        except Exception:
            # A bot cannot message an operator who has never opened a private chat with it.
            logger.warning("Could not send profile onboarding reminder to configured operator.")


def create_dispatcher(settings: Settings, store: VacancyStore) -> Dispatcher:
    dp = Dispatcher()
    resume_storage = ResumeStorage(settings.resume_storage_dir, settings.resume_max_size_bytes)
    profile_service = ProfileService(store, resume_storage)
    browser_worker = BrowserWorker(
        settings.browser_profile_dir,
        settings.application_allowed_domains,
        settings.browser_headless,
        settings.browser_timeout_seconds,
    )

    def profile_operator_from_message(message: Message) -> int | None:
        user_id = message.from_user.id if message.from_user else None
        return user_id if is_profile_operator(user_id, settings.operator_user_ids) else None

    def profile_operator_from_callback(callback: CallbackQuery) -> int | None:
        user_id = callback.from_user.id if callback.from_user else None
        return user_id if is_profile_operator(user_id, settings.operator_user_ids) else None

    async def deny_profile_message(message: Message) -> None:
        await message.answer("Профиль доступен только пользователю из OPERATOR_USER_IDS.")

    async def deny_profile_callback(callback: CallbackQuery) -> None:
        await callback.answer("Профиль доступен только оператору.", show_alert=True)

    @dp.message(Command("profile"))
    async def profile_command(message: Message, state: FSMContext) -> None:
        operator_user_id = profile_operator_from_message(message)
        if operator_user_id is None:
            await deny_profile_message(message)
            return
        await state.clear()
        await message.answer(format_profile_summary(store.get_operator_profile(operator_user_id)), reply_markup=profile_menu())

    @dp.message(Command("queue_resume_id"))
    async def queue_resume_id_command(message: Message) -> None:
        operator_user_id = profile_operator_from_message(message)
        if operator_user_id is None or message.chat.type != ChatType.PRIVATE:
            await deny_profile_message(message)
            return
        await message.answer(queue_resume_id_text(store.get_operator_profile(operator_user_id)))

    @dp.callback_query(F.data == "profile:edit")
    async def profile_edit(callback: CallbackQuery, state: FSMContext) -> None:
        operator_user_id = profile_operator_from_callback(callback)
        if operator_user_id is None:
            await deny_profile_callback(callback)
            return
        await callback.answer()
        profile = store.get_operator_profile(operator_user_id) or OperatorProfile(operator_user_id=operator_user_id)
        await state.set_state(ProfileForm.full_name)
        await state.update_data(profile=profile)
        await callback.message.answer(_profile_prompt("full_name"))

    @dp.message(ProfileForm.full_name, F.text)
    async def profile_full_name(message: Message, state: FSMContext) -> None:
        await _capture_profile_field(message, state, "full_name", ProfileForm.email)

    @dp.message(ProfileForm.email, F.text)
    async def profile_email(message: Message, state: FSMContext) -> None:
        await _capture_profile_field(message, state, "email", ProfileForm.phone)

    @dp.message(ProfileForm.phone, F.text)
    async def profile_phone(message: Message, state: FSMContext) -> None:
        await _capture_profile_field(message, state, "phone", ProfileForm.desired_salary)

    @dp.message(ProfileForm.desired_salary, F.text)
    async def profile_desired_salary(message: Message, state: FSMContext) -> None:
        await _capture_profile_field(message, state, "desired_salary", ProfileForm.location)

    @dp.message(ProfileForm.location, F.text)
    async def profile_location(message: Message, state: FSMContext) -> None:
        await _capture_profile_field(message, state, "location", ProfileForm.work_format)

    @dp.message(ProfileForm.work_format, F.text)
    async def profile_work_format(message: Message, state: FSMContext) -> None:
        await _capture_profile_field(message, state, "work_format", ProfileForm.employment_type)

    @dp.message(ProfileForm.employment_type, F.text)
    async def profile_employment_type(message: Message, state: FSMContext) -> None:
        await _capture_profile_field(message, state, "employment_type", ProfileForm.extra_fields)

    @dp.message(ProfileForm.extra_fields, F.text)
    async def profile_extra_fields(message: Message, state: FSMContext) -> None:
        if await _cancel_profile_edit(message, state):
            return
        profile = (await state.get_data())["profile"]
        text = message.text or ""
        if text == DONE_TEXT or text == SKIP_TEXT:
            store.save_operator_profile(profile)
            await state.clear()
            await message.answer("Профиль сохранён. Резюме можно загрузить через /profile.", reply_markup=profile_menu())
            return
        try:
            name, value = parse_extra_field(text)
            profile = profile_with_extra_field(profile, name, value)
        except ValueError as exc:
            await message.answer(str(exc))
            return
        await state.update_data(profile=profile)
        await message.answer("Поле сохранено. Добавьте ещё одно или нажмите «Готово».")

    @dp.callback_query(F.data == "profile:resume")
    async def profile_resume(callback: CallbackQuery, state: FSMContext) -> None:
        if profile_operator_from_callback(callback) is None:
            await deny_profile_callback(callback)
            return
        await callback.answer()
        await state.set_state(ProfileForm.resume)
        await callback.message.answer(
            "Отправьте файл резюме в PDF или DOCX. Чтобы отменить, отправьте «Отмена»."
        )

    @dp.message(ProfileForm.resume, F.document)
    async def profile_resume_upload(message: Message, bot: Bot, state: FSMContext) -> None:
        operator_user_id = profile_operator_from_message(message)
        if operator_user_id is None:
            await state.clear()
            await deny_profile_message(message)
            return
        document = message.document
        if document is None or document.file_size is None or document.file_size > settings.resume_max_size_bytes:
            await message.answer("Файл резюме превышает допустимый размер.")
            return
        content = BytesIO()
        try:
            await bot.download(document, destination=content)
            profile_service.save_resume(
                operator_user_id,
                document.file_name or "",
                content.getvalue(),
                telegram_file_id=document.file_id,
            )
        except ValueError as exc:
            await message.answer(str(exc))
            return
        except Exception:
            logger.exception("Resume download failed")
            await message.answer("Не удалось сохранить файл резюме. Попробуйте ещё раз.")
            return

        await state.clear()
        await message.answer("Резюме сохранено. Текст будет извлекаться на следующем этапе.", reply_markup=profile_menu())

    @dp.message(ProfileForm.resume)
    async def profile_resume_requires_document(message: Message, state: FSMContext) -> None:
        if message.text == CANCEL_TEXT:
            await state.clear()
            await message.answer("Загрузка резюме отменена.", reply_markup=profile_menu())
            return
        await message.answer("Отправьте PDF/DOCX как документ или «Отмена».")

    @dp.callback_query(F.data == "profile:delete")
    async def profile_delete(callback: CallbackQuery) -> None:
        if profile_operator_from_callback(callback) is None:
            await deny_profile_callback(callback)
            return
        await callback.answer()
        await callback.message.answer(
            "Удалить профиль и локальный файл резюме? Это действие нельзя отменить.",
            reply_markup=profile_confirm_delete_menu(),
        )

    @dp.callback_query(F.data == "profile:delete:cancel")
    async def profile_delete_cancel(callback: CallbackQuery) -> None:
        if profile_operator_from_callback(callback) is None:
            await deny_profile_callback(callback)
            return
        await callback.answer("Удаление отменено.")
        await callback.message.answer("Удаление профиля отменено.", reply_markup=profile_menu())

    @dp.callback_query(F.data == "profile:delete:confirm")
    async def profile_delete_confirm(callback: CallbackQuery, state: FSMContext) -> None:
        operator_user_id = profile_operator_from_callback(callback)
        if operator_user_id is None:
            await deny_profile_callback(callback)
            return
        await callback.answer()
        if not profile_service.delete_profile(operator_user_id):
            await callback.message.answer("Профиль уже удалён.", reply_markup=profile_menu())
            return
        await state.clear()
        await callback.message.answer("Профиль удалён.", reply_markup=profile_menu())

    @dp.callback_query(F.data.startswith(APPLICATION_CALLBACK_PREFIX))
    async def application_button_pending(callback: CallbackQuery, bot: Bot) -> None:
        if not is_profile_operator(callback.from_user.id if callback.from_user else None, settings.operator_user_ids):
            await callback.answer("Отклик доступен только оператору.", show_alert=True)
            return
        vacancy_id = (callback.data or "").removeprefix(APPLICATION_CALLBACK_PREFIX)
        result = store.create_application(callback.from_user.id, vacancy_id)
        if result is None:
            await callback.answer("Вакансия больше недоступна в локальной базе.", show_alert=True)
            return
        application, created = result
        if application.status == "failed":
            notified = await send_application_result_notification(
                bot,
                callback.from_user.id,
                application.status,
                application.vacancy_url,
                error_description=application.error_description,
            )
            message = (
                "Результат отправлен вам в личный чат."
                if notified
                else "Не удалось отправить результат. Откройте личный чат с ботом и нажмите Start."
            )
            await callback.answer(message, show_alert=True)
            return
        if created and application.vacancy_url:
            store.update_application_status(application.application_id, "queued")
            prepared_notified = await send_application_prepared_notification(
                bot,
                callback.from_user.id,
                application.vacancy_url,
            )
            prepared_message = (
                "Отклик подготовлен."
                if prepared_notified
                else "Отклик подготовлен. Откройте личный чат с ботом, чтобы получать сообщения."
            )
            await callback.answer(prepared_message, show_alert=not prepared_notified)
            profile = store.get_operator_profile(callback.from_user.id)
            resume_path = (
                resume_storage.path_for(profile.resume_stored_name)
                if profile and profile.resume_stored_name
                else None
            )
            inspection = await browser_worker.prepare_application(application.vacancy_url, profile, resume_path)
            store.update_application_status(application.application_id, inspection.status, inspection.error)
            await send_application_result_notification(
                bot,
                callback.from_user.id,
                inspection.status,
                application.vacancy_url,
                missing_fields=inspection.missing_fields,
                error_description=inspection.error,
            )
            return
        notified = await send_application_result_notification(
            bot,
            callback.from_user.id,
            application.status,
            application.vacancy_url,
            error_description=application.error_description,
        )
        message = (
            "Актуальный результат отправлен вам в личный чат."
            if notified
            else "Не удалось отправить результат. Откройте личный чат с ботом и нажмите Start."
        )
        await callback.answer(message, show_alert=True)

    @dp.message(Command("start"))
    async def start(message: Message) -> None:
        operator_user_id = profile_operator_from_message(message)
        profile = store.get_operator_profile(operator_user_id) if operator_user_id is not None else None
        if operator_user_id is not None and needs_profile_onboarding(profile):
            await message.answer(profile_onboarding_text(profile), reply_markup=profile_menu())
            return
        await message.answer(
            "Пришли или перешли мне вакансию. Я опубликую ее в целевой канал "
            "как карточку или скопирую оригинал, в зависимости от FORWARDED_MODE."
        )

    @dp.message(Command("help"))
    async def help_command(message: Message) -> None:
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
            reply_markup=application_button(vacancy, queued=settings.application_queue_enabled),
        )
        store.mark_published(vacancy)
        await message.reply("Опубликовал вакансию в канал.")

    return dp


def _profile_prompt(field_name: str) -> str:
    label = dict(PROFILE_FIELDS)[field_name]
    return f"{label}. Отправьте значение, «{SKIP_TEXT}» или «{CANCEL_TEXT}»."


async def _capture_profile_field(
    message: Message, state: FSMContext, field_name: str, next_state: State
) -> None:
    if await _cancel_profile_edit(message, state):
        return
    try:
        value = clean_profile_value(message.text or "")
    except ValueError as exc:
        await message.answer(str(exc))
        return
    profile = profile_with_field((await state.get_data())["profile"], field_name, value)
    await state.update_data(profile=profile)
    await state.set_state(next_state)
    if next_state == ProfileForm.extra_fields:
        await message.answer(
            f"Добавьте дополнительные поля в формате «название: значение». Нажмите «{DONE_TEXT}», когда закончите, "
            f"или «{SKIP_TEXT}», если дополнительных полей нет."
        )
        return
    await message.answer(_profile_prompt(next_state.state.rsplit(":", maxsplit=1)[-1]))


async def _cancel_profile_edit(message: Message, state: FSMContext) -> bool:
    if message.text != CANCEL_TEXT:
        return False
    await state.clear()
    await message.answer("Редактирование профиля отменено.", reply_markup=profile_menu())
    return True


def _message_is_authorized(message: Message, settings: Settings) -> bool:
    user_id = message.from_user.id if message.from_user else None
    return is_authorized_user(user_id, settings.operator_user_ids)


async def run_bot(settings: Settings) -> None:
    settings.require_bot_polling()
    logging.basicConfig(level=logging.INFO)

    lock_path = bot_run_lock_path(settings.database_path, settings.telegram_bot_token)
    with SingleInstanceLock(lock_path):
        store = VacancyStore(settings.database_path)
        bot = Bot(
            token=settings.telegram_bot_token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        dp = create_dispatcher(settings, store)
        await send_profile_onboarding_reminders(bot, settings, store)
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
