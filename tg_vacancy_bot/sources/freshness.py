from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timedelta

from tg_vacancy_bot.models import Vacancy


def filter_fresh_vacancies(
    vacancies: Iterable[Vacancy],
    *,
    max_age_hours: int,
    current_time: datetime,
    require_published_at: bool = False,
) -> list[Vacancy]:
    if max_age_hours <= 0:
        return [vacancy for vacancy in vacancies if vacancy.published_at is not None or not require_published_at]

    cutoff = current_time - timedelta(hours=max_age_hours)
    fresh: list[Vacancy] = []
    for vacancy in vacancies:
        if vacancy.published_at is None:
            if not require_published_at:
                fresh.append(vacancy)
        elif vacancy.published_at >= cutoff:
            fresh.append(vacancy)
    return fresh
