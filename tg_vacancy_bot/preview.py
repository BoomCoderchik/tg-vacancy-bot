from __future__ import annotations

from .config import Settings
from .description_localization import DescriptionLocalizer, localize_vacancy_description
from .formatting import format_vacancy_card
from .intake import looks_like_vacancy_message
from .models import Vacancy
from .parser import parse_message_to_vacancy


def parse_publishable_message(text: str) -> Vacancy:
    if not looks_like_vacancy_message(text):
        raise RuntimeError("Message does not look like an IT vacancy.")
    return parse_message_to_vacancy(text)


def preview_message_card(text: str) -> str:
    return format_vacancy_card(parse_publishable_message(text))


async def preview_message_card_async(
    text: str,
    settings: Settings,
    localizer: DescriptionLocalizer | None = None,
) -> str:
    vacancy = parse_publishable_message(text)
    vacancy = await localize_vacancy_description(vacancy, settings, localizer=localizer)
    return format_vacancy_card(vacancy)
