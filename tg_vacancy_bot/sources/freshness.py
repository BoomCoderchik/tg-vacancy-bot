from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timedelta

from tg_vacancy_bot.models import Vacancy


def filter_fresh_vacancies(
    vacancies: Iterable[Vacancy],
    *,
    max_age_hours: int,
    current_time: datetime,
) -> list[Vacancy]:
    if max_age_hours <= 0:
        return list(vacancies)

    cutoff = current_time - timedelta(hours=max_age_hours)
    fresh: list[Vacancy] = []
    for vacancy in vacancies:
        if vacancy.published_at is None or vacancy.published_at >= cutoff:
            fresh.append(vacancy)
    return fresh
