from __future__ import annotations

from dataclasses import replace
from typing import Protocol

from .config import Settings
from .models import Vacancy


MAX_LOCALIZED_DESCRIPTION_CHARS = 700
MAX_OUTPUT_TOKENS = 260

LOCALIZATION_INSTRUCTIONS = """
Ты редактор Telegram-канала с IT-вакансиями.
Переведи на русский и сожми только исходное описание вакансии из следующего сообщения.
Не добавляй зарплату, бонусы, соцпакет, стек, график, компанию, локацию, требования или преимущества, если они не указаны прямо в исходном описании.
Не используй сведения из заголовка, полей карточки, ссылки или своих предположений.
Если в описании мало фактов, напиши короткий перевод только этих фактов.
Пиши одним коротким абзацем до 2 предложений, без маркированных списков, вступлений и комментариев.
""".strip()


class DescriptionLocalizer(Protocol):
    async def localize(self, description: str) -> str:
        raise NotImplementedError


class OpenAIDescriptionLocalizer:
    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = "",
        client: object | None = None,
    ) -> None:
        self.model = model
        if client is None:
            try:
                from openai import AsyncOpenAI
            except ImportError as exc:
                raise RuntimeError("The openai package is required for description localization.") from exc
            client_kwargs = {"api_key": api_key}
            if base_url:
                client_kwargs["base_url"] = base_url
            client = AsyncOpenAI(**client_kwargs)
        self.client = client

    async def localize(self, description: str) -> str:
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": LOCALIZATION_INSTRUCTIONS},
                    {"role": "user", "content": description},
                ],
                max_tokens=MAX_OUTPUT_TOKENS,
                temperature=0.2,
            )
        except Exception as exc:
            raise RuntimeError(format_openai_error(exc)) from exc
        text = normalize_localized_description(response.choices[0].message.content or "")
        if not text:
            raise RuntimeError("OpenAI returned an empty localized description.")
        return text


async def localize_vacancy_description(
    vacancy: Vacancy,
    settings: Settings,
    localizer: DescriptionLocalizer | None = None,
) -> Vacancy:
    if not settings.localize_descriptions or not vacancy.description.strip():
        return vacancy
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required when LOCALIZE_DESCRIPTIONS=true.")

    localizer = localizer or OpenAIDescriptionLocalizer(
        api_key=settings.openai_api_key,
        model=settings.openai_model,
        base_url=settings.openai_base_url,
    )
    description = await localizer.localize(vacancy.description)
    return replace(vacancy, description=description)


def normalize_localized_description(text: str) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= MAX_LOCALIZED_DESCRIPTION_CHARS:
        return normalized
    return normalized[: MAX_LOCALIZED_DESCRIPTION_CHARS - 1].rstrip() + "..."


def format_openai_error(exc: Exception) -> str:
    message = str(exc)
    if "insufficient_quota" in message:
        return "OpenAI API quota is exhausted. Check the OpenAI account billing or quota before publishing localized descriptions."
    return f"OpenAI description localization failed: {message}"
