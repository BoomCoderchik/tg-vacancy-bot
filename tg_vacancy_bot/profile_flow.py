from __future__ import annotations

from dataclasses import replace
from html import escape

from .models import OperatorProfile


SKIP_TEXT = "Пропустить"
CANCEL_TEXT = "Отмена"
DONE_TEXT = "Готово"
MAX_PROFILE_VALUE_LENGTH = 256
MAX_EXTRA_FIELD_NAME_LENGTH = 64
MAX_EXTRA_FIELDS = 20

PROFILE_FIELDS = (
    ("full_name", "Ваше имя"),
    ("email", "Email"),
    ("phone", "Телефон"),
    ("desired_salary", "Желаемая зарплата"),
    ("location", "Локация"),
    ("work_format", "Формат работы (например, удалённо)"),
    ("employment_type", "Тип занятости"),
)


def is_profile_operator(user_id: int | None, operator_user_ids: tuple[int, ...]) -> bool:
    """Profiles are unavailable until the private operator allowlist is configured."""
    return user_id is not None and bool(operator_user_ids) and user_id in operator_user_ids


def clean_profile_value(value: str) -> str | None:
    value = value.strip()
    if not value or value == SKIP_TEXT:
        return None
    if len(value) > MAX_PROFILE_VALUE_LENGTH:
        raise ValueError(f"Значение должно быть не длиннее {MAX_PROFILE_VALUE_LENGTH} символов.")
    return value


def parse_extra_field(value: str) -> tuple[str, str]:
    if ":" not in value:
        raise ValueError("Введите дополнительное поле в формате «название: значение».")
    name, field_value = (part.strip() for part in value.split(":", maxsplit=1))
    if not name or not field_value:
        raise ValueError("Название и значение дополнительного поля не должны быть пустыми.")
    if len(name) > MAX_EXTRA_FIELD_NAME_LENGTH:
        raise ValueError(f"Название поля должно быть не длиннее {MAX_EXTRA_FIELD_NAME_LENGTH} символов.")
    if len(field_value) > MAX_PROFILE_VALUE_LENGTH:
        raise ValueError(f"Значение должно быть не длиннее {MAX_PROFILE_VALUE_LENGTH} символов.")
    return name, field_value


def profile_with_field(profile: OperatorProfile, field_name: str, value: str | None) -> OperatorProfile:
    if field_name not in {name for name, _ in PROFILE_FIELDS}:
        raise ValueError(f"Unknown profile field: {field_name}")
    return replace(profile, **{field_name: value})


def profile_with_extra_field(profile: OperatorProfile, name: str, value: str) -> OperatorProfile:
    extra_fields = {**profile.extra_fields, name: value}
    if len(extra_fields) > MAX_EXTRA_FIELDS:
        raise ValueError(f"Можно сохранить не больше {MAX_EXTRA_FIELDS} дополнительных полей.")
    return replace(profile, extra_fields=extra_fields)


def format_profile_summary(profile: OperatorProfile | None) -> str:
    if profile is None:
        return "<b>Профиль</b>\nПока не заполнен. Выберите действие ниже."

    values = [
        ("Имя", profile.full_name),
        ("Email", profile.email),
        ("Телефон", profile.phone),
        ("Желаемая зарплата", profile.desired_salary),
        ("Локация", profile.location),
        ("Формат работы", profile.work_format),
        ("Тип занятости", profile.employment_type),
        ("Резюме", profile.resume_original_name),
    ]
    lines = ["<b>Профиль</b>"]
    lines.extend(f"<b>{label}:</b> {escape(value) if value else 'не указано'}" for label, value in values)
    if profile.extra_fields:
        lines.append("<b>Дополнительные поля:</b>")
        lines.extend(f"• {escape(name)}: {escape(value)}" for name, value in profile.extra_fields.items())
    return "\n".join(lines)
