from __future__ import annotations

from collections.abc import Iterable

from .sources.filters import evaluate_vacancy_policy


def looks_like_vacancy_message(
    text: str,
    specialty: str | Iterable[str] | None = None,
    grade: str | Iterable[str] | None = None,
) -> bool:
    normalized = " ".join((text or "").split())
    if len(normalized) < 24:
        return False
    return evaluate_vacancy_policy(normalized, specialty, grade).allowed
