from __future__ import annotations

from .sources.filters import evaluate_vacancy_policy


def looks_like_vacancy_message(text: str) -> bool:
    normalized = " ".join((text or "").split())
    if len(normalized) < 24:
        return False
    return evaluate_vacancy_policy(normalized).allowed
