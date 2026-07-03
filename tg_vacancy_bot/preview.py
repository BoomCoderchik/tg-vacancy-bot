from __future__ import annotations

from .formatting import format_vacancy_card
from .intake import looks_like_vacancy_message
from .parser import parse_message_to_vacancy


def preview_message_card(text: str) -> str:
    if not looks_like_vacancy_message(text):
        raise RuntimeError("Message does not look like an IT vacancy.")
    return format_vacancy_card(parse_message_to_vacancy(text))
