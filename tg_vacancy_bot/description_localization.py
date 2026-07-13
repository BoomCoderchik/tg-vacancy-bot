from __future__ import annotations

from dataclasses import replace
from difflib import SequenceMatcher
import re
from typing import Protocol

from .config import Settings
from .models import Vacancy


MAX_LOCALIZED_DESCRIPTION_CHARS = 700
MAX_OUTPUT_TOKENS = 260
CYRILLIC_RE = re.compile(r"[\u0400-\u04FF]")
LETTER_RE = re.compile(r"[A-Za-z\u0400-\u04FF]")
MIN_RUSSIAN_CYRILLIC_RATIO = 0.35
MAX_ORIGINAL_SIMILARITY = 0.82

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
        fallback_models: tuple[str, ...] = (),
        base_url: str = "",
        client: object | None = None,
    ) -> None:
        self.model = model
        self.fallback_models = fallback_models
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
        errors: list[str] = []
        for model in unique_models((self.model, *self.fallback_models)):
            try:
                response = await self.client.chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": LOCALIZATION_INSTRUCTIONS},
                        {"role": "user", "content": description},
                    ],
                    max_tokens=MAX_OUTPUT_TOKENS,
                    temperature=0.2,
                )
            except Exception as exc:
                errors.append(format_openai_error(exc))
                continue

            content = extract_response_content(response)
            if content is None:
                errors.append(f"{model} returned an invalid response without message content.")
                continue

            text = normalize_localized_description(content)
            rejection_reason = localized_description_rejection_reason(description, text)
            if rejection_reason is None:
                return text
            errors.append(f"{model} {rejection_reason}")

        if errors == [f"{self.model} returned an empty localized description."]:
            raise RuntimeError("OpenAI returned an empty localized description.")
        raise RuntimeError(f"OpenAI description localization failed after fallback attempts: {'; '.join(errors)}")


async def localize_vacancy_description(
    vacancy: Vacancy,
    settings: Settings,
    localizer: DescriptionLocalizer | None = None,
) -> Vacancy:
    if not settings.localize_descriptions or not vacancy.description.strip():
        return vacancy
    if not settings.localization_api_key:
        raise RuntimeError(f"{settings.localization_api_key_name} is required when LOCALIZE_DESCRIPTIONS=true.")
    # Search snippets are often already Russian. Avoid spending a model call
    # on text that does not need translation, especially when post discovery
    # is intentionally configured to collect a large candidate pool.
    if not source_requires_russian_translation(vacancy.description):
        return vacancy

    localizer = localizer or OpenAIDescriptionLocalizer(
        api_key=settings.localization_api_key,
        model=settings.localization_model,
        fallback_models=settings.localization_fallback_models,
        base_url=settings.localization_base_url,
    )
    description = await localizer.localize(vacancy.description)
    return replace(vacancy, description=description)


def normalize_localized_description(text: str) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= MAX_LOCALIZED_DESCRIPTION_CHARS:
        return normalized
    return normalized[: MAX_LOCALIZED_DESCRIPTION_CHARS - 1].rstrip() + "..."


def extract_response_content(response: object) -> str | None:
    """Return assistant content when an API response has the expected shape."""
    choices = getattr(response, "choices", None)
    if not choices:
        return None
    first_choice = choices[0]
    message = getattr(first_choice, "message", None)
    content = getattr(message, "content", None)
    return content if isinstance(content, str) else None


def localized_description_rejection_reason(original: str, localized: str) -> str | None:
    if not localized:
        return "returned an empty localized description."
    if not source_requires_russian_translation(original):
        return None
    if not looks_like_russian(localized):
        return "returned text that is not Russian."
    if text_similarity(original, localized) >= MAX_ORIGINAL_SIMILARITY:
        return "returned the original description instead of a Russian translation."
    return None


def source_requires_russian_translation(text: str) -> bool:
    letters = LETTER_RE.findall(text)
    if not letters:
        return False
    cyrillic_count = len(CYRILLIC_RE.findall(text))
    return cyrillic_count / len(letters) < MIN_RUSSIAN_CYRILLIC_RATIO


def looks_like_russian(text: str) -> bool:
    letters = LETTER_RE.findall(text)
    if not letters:
        return False
    cyrillic_count = len(CYRILLIC_RE.findall(text))
    return cyrillic_count / len(letters) >= MIN_RUSSIAN_CYRILLIC_RATIO


def text_similarity(left: str, right: str) -> float:
    return SequenceMatcher(None, comparable_text(left), comparable_text(right)).ratio()


def comparable_text(text: str) -> str:
    return " ".join(re.findall(r"[a-zA-Z\u0400-\u04FF0-9]+", text.lower()))


def unique_models(models: tuple[str, ...]) -> tuple[str, ...]:
    result = []
    for model in models:
        if model and model not in result:
            result.append(model)
    return tuple(result)


def format_openai_error(exc: Exception) -> str:
    message = str(exc)
    if "insufficient_quota" in message:
        return "OpenAI API quota is exhausted. Check the OpenAI account billing or quota before publishing localized descriptions."
    return f"OpenAI description localization failed: {message}"
