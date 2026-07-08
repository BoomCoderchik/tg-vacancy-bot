from html import escape

from .models import Vacancy


MAX_DESCRIPTION_CHARS = 1400


def trim_text(text: str, max_chars: int) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= max_chars:
        return normalized
    return normalized[: max_chars - 1].rstrip() + "..."


def format_vacancy_card(vacancy: Vacancy) -> str:
    title = escape(vacancy.title or "IT Vacancy")
    lines = [
        f"💼 <b>{title}</b>",
    ]

    if vacancy.company:
        lines.extend(["", format_field("🏢", "Компания", vacancy.company)])

    if vacancy.location:
        lines.extend(["", format_field("📍", "Локация", vacancy.location)])

    if vacancy.salary:
        lines.extend(["", format_field("💰", "Зарплата", vacancy.salary)])

    stack = ", ".join(vacancy.stack[:18]) if vacancy.stack else "—"
    lines.extend(["", format_field("🧠", "Стек", stack)])

    description = trim_text(vacancy.description, MAX_DESCRIPTION_CHARS)
    if description:
        lines.extend(["", "<b>Описание</b>", escape(description)])

    if vacancy.url:
        lines.extend(["", f'🔗 <a href="{escape(vacancy.url)}"><b>Смотреть вакансию</b></a>'])

    lines.append(f"▫️ Источник: {escape(vacancy.source)}")
    return "\n".join(lines)


def format_field(icon: str, label: str, value: str) -> str:
    return f"{icon} <b>{label}</b>: {escape(value)}"
