from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from .models import Vacancy
from .storage import VacancyStore


APPLICATION_CALLBACK_PREFIX = "apply:"


def application_callback_data(vacancy: Vacancy) -> str:
    """Return a Telegram-safe callback value without exposing the vacancy URL."""
    return f"{APPLICATION_CALLBACK_PREFIX}{VacancyStore.fingerprint(vacancy)}"


def application_button(vacancy: Vacancy, *, queued: bool = False) -> InlineKeyboardMarkup:
    text = "Откликнуться (очередь)" if queued else "Откликнуться"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=text, callback_data=application_callback_data(vacancy))]
        ]
    )
