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
        "<b>IT Job Board</b>",
        f"💼 <b>{title}</b>",
    ]

    if vacancy.company:
        lines.extend(["", f"🏢 Компания: {escape(vacancy.company)}"])

    if vacancy.location:
        lines.extend(["", f"📍 Локация: {escape(vacancy.location)}"])

    if vacancy.salary:
        lines.extend(["", f"💰 Зарплата: {escape(vacancy.salary)}"])

    if vacancy.stack:
        stack = ", ".join(vacancy.stack[:18])
        lines.extend(["", f"🧠 Стек: {escape(stack)}"])

    description = trim_text(vacancy.description, MAX_DESCRIPTION_CHARS)
    if description:
        lines.extend(["", "Описание:", escape(description)])

    if vacancy.url:
        lines.extend(["", f'🔗 <a href="{escape(vacancy.url)}">Смотреть вакансию</a>'])

    lines.append(f"Источник: {escape(vacancy.source)}")
    return "\n".join(lines)
