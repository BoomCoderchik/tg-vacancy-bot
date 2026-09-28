from __future__ import annotations

import asyncio
from dataclasses import replace
from io import BytesIO
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from .access_control import is_authorized_user, unauthorized_reply_text
from .config import Settings
from .description_localization import localize_vacancy_description
from .formatting import format_vacancy_card
from .github_filter_sync import sync_vacancy_filter_to_github
from .intake import looks_like_vacancy_message
from .preview import parse_publishable_message
from .runtime_lock import SingleInstanceLock, bot_run_lock_path
from .models import OperatorProfile, VacancyFilter
from .sources.filters import (
    DEFAULT_GRADE,
    DEFAULT_SPECIALTY,
    GRADE_LABELS_RU,
    SPECIALTY_LABELS_RU,
    VALID_GRADES,
    VALID_SPECIALTIES,
)
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


class FilterForm(StatesGroup):
    specialty = State()
    grade = State()
    confirm = State()


def format_filter_text(vacancy_filter: VacancyFilter | None = None) -> str:
    if vacancy_filter and vacancy_filter.specialties:
        specialties = [item for item in vacancy_filter.specialties if item in SPECIALTY_LABELS_RU]
    else:
        specialties = [DEFAULT_SPECIALTY]
    if vacancy_filter and vacancy_filter.grades:
        grades = [item for item in vacancy_filter.grades if item in GRADE_LABELS_RU]
    else:
        grades = [DEFAULT_GRADE]
    specialty_labels = ", ".join(SPECIALTY_LABELS_RU[item] for item in specialties)
    grade_labels = ", ".join(GRADE_LABELS_RU[item] for item in grades)
    return f"{specialty_labels} • {grade_labels}"


def format_selection_labels(selected: list[str], labels: dict[str, str]) -> str:
    if not selected:
        return "ничего не выбрано"
    return ", ".join(labels.get(item, item) for item in selected)


def specialty_panel_text(selected: list[str]) -> str:
    return (
        "Шаг 1/2 — специальности (можно выбрать несколько).\n"
        f"Выбрано: {format_selection_labels(selected, SPECIALTY_LABELS_RU)}.\n\n"
        "Нажимайте кнопки, чтобы отметить или снять выбор, затем — «Далее»."
    )


def grade_panel_text(selected: list[str]) -> str:
    return (
        "Шаг 2/2 — грейды (можно выбрать несколько).\n"
        f"Выбрано: {format_selection_labels(selected, GRADE_LABELS_RU)}.\n\n"
        "Нажимайте кнопки, чтобы отметить или снять выбор, затем — «Далее»."
    )


def specialty_keyboard(selected: list[str] | tuple[str, ...]) -> InlineKeyboardMarkup:
    chosen = set(selected)
    buttons = [
        InlineKeyboardButton(
            text=f"{'✅ ' if specialty in chosen else ''}{SPECIALTY_LABELS_RU[specialty]}",
            callback_data=f"fspec:{specialty}",
        )
        for specialty in VALID_SPECIALTIES
    ]
    rows = [buttons[index : index + 2] for index in range(0, len(buttons), 2)]
    rows.append([InlineKeyboardButton(text="➡️ Далее: грейды", callback_data="filter:next")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def grade_keyboard(selected: list[str] | tuple[str, ...]) -> InlineKeyboardMarkup:
    chosen = set(selected)
    buttons = [
        InlineKeyboardButton(
            text=f"{'✅ ' if grade in chosen else ''}{GRADE_LABELS_RU[grade]}",
            callback_data=f"fgrade:{grade}",
        )
        for grade in VALID_GRADES
    ]
    rows = [buttons[index : index + 2] for index in range(0, len(buttons), 2)]
    rows.append(
        [
            InlineKeyboardButton(text="↩️ Назад", callback_data="filter:back"),
            InlineKeyboardButton(text="➡️ Далее", callback_data="filter:next"),
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def filter_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Применить", callback_data="filter:confirm")],
            [InlineKeyboardButton(text="↩️ Изменить", callback_data="filter:restart")],
        ]
    )


def build_status_text(settings: Settings, vacancy_filter: VacancyFilter | None = None) -> str:
    source_states = [
        f"LinkedInPosts={_linkedin_post_search_state(settings)}",
        f"LinkedInPostScraper={_linkedin_post_scraper_state(settings)}",
        f"LinkedInHeadless={_linkedin_headless_state(settings)}",
        f"LinkedInPostGuest={'on' if settings.enable_linkedin_post_guest else 'off'}",
    ]
    return "\n".join(
        [
            "TG Vacancy Bot status",
            f"Forwarded mode: {settings.forwarded_mode}",
            f"Target chat: {settings.target_chat_id or 'not configured'}",
            f"Vacancy filter: {format_filter_text(vacancy_filter)}",
            f"Operator allowlist: {'on' if settings.operator_user_ids else 'empty (publishing locked)'}",
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
    if not settings.serpapi_api_key:
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


def create_dispatcher(settings: Settings, store: VacancyStore) -> Dispatcher:
    dp = Dispatcher()
    resume_storage = ResumeStorage(settings.resume_storage_dir, settings.resume_max_size_bytes)
    profile_service = ProfileService(store, resume_storage)

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

    @dp.message(Command("start"))
    async def start(message: Message, state: FSMContext) -> None:
        if not _message_is_authorized(message, settings):
            await message.answer(
                "Пришли или перешли мне вакансию. Я опубликую ее тебе в личку "
                "как карточку или скопирую оригинал, в зависимости от FORWARDED_MODE.\n\n"
                + unauthorized_reply_text(settings.operator_user_ids)
            )
            return
        await state.clear()
        current = store.get_vacancy_filter()
        await state.update_data(
            specialties=list(current.specialties),
            grades=list(current.grades),
        )
        await state.set_state(FilterForm.specialty)
        await message.answer(
            "Выбери, какие вакансии парсить.\n\n"
            f"Текущий фильтр: {format_filter_text(current)}.\n\n"
            f"{specialty_panel_text(list(current.specialties))}",
            reply_markup=specialty_keyboard(list(current.specialties)),
        )

    @dp.message(Command("help"))
    async def help_command(message: Message) -> None:
        await message.answer(
            "Пришли или перешли мне вакансию. Я опубликую ее тебе в личку "
            "как карточку или скопирую оригинал, в зависимости от FORWARDED_MODE."
        )

    @dp.message(Command("status"))
    async def status(message: Message) -> None:
        if not _message_is_authorized(message, settings):
            await message.reply(unauthorized_reply_text(settings.operator_user_ids))
            return
        await message.answer(build_status_text(settings, store.get_vacancy_filter()))

    @dp.message(Command("filters"))
    async def filters_command(message: Message, state: FSMContext) -> None:
        if not _message_is_authorized(message, settings):
            await message.reply(unauthorized_reply_text(settings.operator_user_ids))
            return
        await state.clear()
        current = store.get_vacancy_filter()
        await state.update_data(
            specialties=list(current.specialties),
            grades=list(current.grades),
        )
        await state.set_state(FilterForm.specialty)
        await message.answer(
            f"Текущий фильтр: {format_filter_text(current)}.\n\n"
            f"{specialty_panel_text(list(current.specialties))}",
            reply_markup=specialty_keyboard(list(current.specialties)),
        )

    @dp.callback_query(FilterForm.specialty, F.data.startswith("fspec:"))
    async def filter_specialty_toggled(callback: CallbackQuery, state: FSMContext) -> None:
        if not _callback_is_authorized(callback, settings):
            await callback.answer(unauthorized_reply_text(settings.operator_user_ids), show_alert=True)
            return
        specialty = (callback.data or "").removeprefix("fspec:").strip().lower()
        if specialty not in VALID_SPECIALTIES:
            await callback.answer("Неизвестная специальность.", show_alert=True)
            return
        data = await state.get_data()
        selected = [item for item in data.get("specialties", []) if item in VALID_SPECIALTIES]
        if specialty in selected:
            selected.remove(specialty)
        else:
            selected.append(specialty)
        await state.update_data(specialties=selected)
        await callback.answer()
        await callback.message.edit_text(
            specialty_panel_text(selected),
            reply_markup=specialty_keyboard(selected),
        )

    @dp.callback_query(FilterForm.specialty, F.data == "filter:next")
    async def filter_specialties_done(callback: CallbackQuery, state: FSMContext) -> None:
        if not _callback_is_authorized(callback, settings):
            await callback.answer(unauthorized_reply_text(settings.operator_user_ids), show_alert=True)
            return
        data = await state.get_data()
        selected = [item for item in data.get("specialties", []) if item in VALID_SPECIALTIES]
        if not selected:
            await callback.answer("Выберите хотя бы одну специальность.", show_alert=True)
            return
        grades = [item for item in data.get("grades", []) if item in VALID_GRADES]
        await state.set_state(FilterForm.grade)
        await callback.answer()
        await callback.message.edit_text(
            grade_panel_text(grades),
            reply_markup=grade_keyboard(grades),
        )

    @dp.callback_query(FilterForm.grade, F.data.startswith("fgrade:"))
    async def filter_grade_toggled(callback: CallbackQuery, state: FSMContext) -> None:
        if not _callback_is_authorized(callback, settings):
            await callback.answer(unauthorized_reply_text(settings.operator_user_ids), show_alert=True)
            return
        grade = (callback.data or "").removeprefix("fgrade:").strip().lower()
        if grade not in VALID_GRADES:
            await callback.answer("Неизвестный грейд.", show_alert=True)
            return
        data = await state.get_data()
        selected = [item for item in data.get("grades", []) if item in VALID_GRADES]
        if grade in selected:
            selected.remove(grade)
        else:
            selected.append(grade)
        await state.update_data(grades=selected)
        await callback.answer()
        await callback.message.edit_text(
            grade_panel_text(selected),
            reply_markup=grade_keyboard(selected),
        )

    @dp.callback_query(FilterForm.grade, F.data == "filter:back")
    async def filter_back_to_specialties(callback: CallbackQuery, state: FSMContext) -> None:
        if not _callback_is_authorized(callback, settings):
            await callback.answer(unauthorized_reply_text(settings.operator_user_ids), show_alert=True)
            return
        data = await state.get_data()
        selected = [item for item in data.get("specialties", []) if item in VALID_SPECIALTIES]
        await state.set_state(FilterForm.specialty)
        await callback.answer()
        await callback.message.edit_text(
            specialty_panel_text(selected),
            reply_markup=specialty_keyboard(selected),
        )

    @dp.callback_query(FilterForm.grade, F.data == "filter:next")
    async def filter_grades_done(callback: CallbackQuery, state: FSMContext) -> None:
        if not _callback_is_authorized(callback, settings):
            await callback.answer(unauthorized_reply_text(settings.operator_user_ids), show_alert=True)
            return
        data = await state.get_data()
        selected_specialties = [item for item in data.get("specialties", []) if item in VALID_SPECIALTIES]
        selected_grades = [item for item in data.get("grades", []) if item in VALID_GRADES]
        if not selected_grades:
            await callback.answer("Выберите хотя бы один грейд.", show_alert=True)
            return
        await state.set_state(FilterForm.confirm)
        await callback.answer()
        preview = VacancyFilter(
            specialties=tuple(selected_specialties),
            grades=tuple(selected_grades),
        )
        await callback.message.edit_text(
            f"Применить фильтр «{format_filter_text(preview)}»?\n"
            "Парситься будут только вакансии под эти специальности и грейды.",
            reply_markup=filter_confirm_keyboard(),
        )

    @dp.callback_query(FilterForm.confirm, F.data == "filter:confirm")
    async def filter_confirmed(callback: CallbackQuery, state: FSMContext) -> None:
        if not _callback_is_authorized(callback, settings):
            await callback.answer(unauthorized_reply_text(settings.operator_user_ids), show_alert=True)
            return
        data = await state.get_data()
        try:
            saved = store.set_vacancy_filter(
                data.get("specialties", []),
                data.get("grades", []),
            )
        except ValueError as exc:
            await callback.answer(str(exc), show_alert=True)
            return
        await state.clear()
        await callback.answer("Фильтр применён.")
        ok, sync_message = await sync_vacancy_filter_to_github(saved, settings)
        if not ok:
            logger.warning("GitHub filter sync: %s", sync_message)
        await callback.message.edit_text(
            f"✅ Фильтр применён: {format_filter_text(saved)}.\n"
            "Теперь парсятся только подходящие вакансии. Посмотреть можно через /status, "
            "изменить — через /filters."
        )

    @dp.callback_query(FilterForm.confirm, F.data == "filter:restart")
    async def filter_restart(callback: CallbackQuery, state: FSMContext) -> None:
        if not _callback_is_authorized(callback, settings):
            await callback.answer(unauthorized_reply_text(settings.operator_user_ids), show_alert=True)
            return
        data = await state.get_data()
        selected = [item for item in data.get("specialties", []) if item in VALID_SPECIALTIES]
        await state.set_state(FilterForm.specialty)
        await callback.answer()
        await callback.message.edit_text(
            specialty_panel_text(selected),
            reply_markup=specialty_keyboard(selected),
        )

    @dp.message(Command("whoami"))
    async def whoami(message: Message) -> None:
        user_id = message.from_user.id if message.from_user else None
        await message.answer(format_whoami_text(user_id))

    @dp.message(F.text | F.caption)
    async def handle_message(message: Message, bot: Bot) -> None:
        if not _message_is_authorized(message, settings):
            await message.reply(unauthorized_reply_text(settings.operator_user_ids))
            return

        active_filter = store.get_vacancy_filter()
        text = message.text or message.caption or ""
        if not looks_like_vacancy_message(text, active_filter.specialties, active_filter.grades):
            await message.reply(
                "I skipped this message because it does not look like an allowed "
                f"{format_filter_text(active_filter)} vacancy."
            )
            return

        if settings.forwarded_mode == "copy":
            await bot.copy_message(
                chat_id=settings.target_chat_id,
                from_chat_id=message.chat.id,
                message_id=message.message_id,
            )
            await message.reply("Скопировал сообщение тебе в личку.")
            return

        vacancy = parse_publishable_message(text, active_filter.specialties, active_filter.grades)
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
        await message.reply("Опубликовал вакансию тебе в личку.")

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


def _callback_is_authorized(callback: CallbackQuery, settings: Settings) -> bool:
    user_id = callback.from_user.id if callback.from_user else None
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
        asyncio.create_task(_sync_filter_on_startup(settings, store))
        polling_task = asyncio.create_task(poll_sources_forever(bot, settings, store))
        polling_task.add_done_callback(_report_polling_task_exit)

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


def _report_polling_task_exit(task: asyncio.Task) -> None:
    """Make an unexpected end of the background polling task visible in logs."""
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        logger.error("Background source polling task stopped unexpectedly.", exc_info=exc)


async def _sync_filter_on_startup(settings: Settings, store: VacancyStore) -> None:
    try:
        active = store.get_vacancy_filter()
    except Exception:
        logger.exception("Could not read the stored filter for GitHub sync on startup.")
        return
    ok, message = await sync_vacancy_filter_to_github(active, settings)
    if ok:
        logger.info("GitHub filter sync on startup: %s", message)
    else:
        logger.warning("GitHub filter sync on startup: %s", message)
