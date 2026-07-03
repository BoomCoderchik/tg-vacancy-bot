from __future__ import annotations

from urllib.parse import urlparse

from .parser import extract_stack, extract_urls
from .sources.filters import looks_like_it_vacancy


JOB_TERMS = [
    "hiring",
    "job",
    "vacancy",
    "role",
    "position",
    "looking for",
    "we are looking",
    "ищем",
    "вакансия",
    "нужен",
    "нужна",
    "требуется",
]

VACANCY_DOMAINS = [
    "linkedin.com",
    "remotive.com",
    "arbeitnow.com",
    "remoteok.com",
    "jooble.org",
    "adzuna.com",
    "news.ycombinator.com",
]


def looks_like_vacancy_message(text: str) -> bool:
    normalized = " ".join((text or "").split())
    if len(normalized) < 24:
        return False

    lower = normalized.lower()
    if looks_like_it_vacancy(normalized):
        return True
    if extract_stack(normalized) and any(term in lower for term in JOB_TERMS):
        return True
    if any(term in lower for term in JOB_TERMS) and any(_is_vacancy_domain(url) for url in extract_urls(normalized)):
        return True
    return False


def _is_vacancy_domain(url: str) -> bool:
    host = urlparse(url).netloc.lower().removeprefix("www.")
    return any(domain in host for domain in VACANCY_DOMAINS)
