"""Russia-wide open-web vacancy search adapter.

Discovers fresh IT vacancies across the whole (mostly Russian) open web using
the same free public search providers as the LinkedIn post scraper, without a
``site:`` restriction. Results flow into the shared publish pipeline (policy
filter, freshness, localization, SQLite dedup); this module never filters by
domain, it only orders collected results by known Russian job-domain hints.
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from urllib.parse import urlsplit
from xml.etree import ElementTree

from bs4 import BeautifulSoup

from tg_vacancy_bot.config import Settings
from tg_vacancy_bot.models import Vacancy
from tg_vacancy_bot.sources.base import SourceAdapter, html_to_text, source_session
from tg_vacancy_bot.sources.dates import parse_relative_source_datetime, parse_source_datetime
from tg_vacancy_bot.sources.filter_queries import RU_JOB_DOMAIN_HINTS
from tg_vacancy_bot.sources.freshness import filter_fresh_vacancies
from tg_vacancy_bot.sources.search_providers import (
    BROWSER_HEADERS,
    SearchHtmlResult,
    _fetch_bing_rss,
    _fetch_search_html,
    _looks_like_search_challenge,
    _normalize_result_url,
    _search_html_results,
    _xml_child_text,
)

logger = logging.getLogger(__name__)

# Own domains of the free search providers: their own result/footer links
# must never be published as vacancies.
_SEARCH_ENGINE_DOMAINS = ("bing.com", "duckduckgo.com", "mojeek.com")
# LinkedIn is covered by dedicated adapters and is excluded here.
_LINKEDIN_DOMAINS = ("linkedin.com",)

_TITLE_BRANDS = (
    r"hh\.ru",
    r"superjob(?:\.ru)?",
    r"career\.habr\.com",
    r"хабр карьер\w*",
    r"хабр",
    r"getmatch",
    r"vc\.ru",
    r"teletype\.in",
    r"rabota\.ru",
    r"работа\.ру",
    r"зарплата\.ру",
    r"work\.ua",
    r"djinni(?:\.co)?",
)
_TITLE_SUFFIX_PATTERN = re.compile(
    r"\s*(?:\||[-–—·:])\s*(?:" + "|".join(_TITLE_BRANDS) + r")\s*$",
    re.IGNORECASE,
)
_TITLE_PREFIX_PATTERN = re.compile(
    r"^\s*(?:(?:" + "|".join(_TITLE_BRANDS) + r")\s*(?:\||[-–—·:])\s*)+",
    re.IGNORECASE,
)

_SPAM_MARKERS = (
    "купить",
    "продажа",
    "снять",
    "аренда",
    "скачать",
    "регистрация",
    "казино",
    "кредит",
    "займ",
    "гороскоп",
)

_STACK_MARKERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("frontend", ("frontend", "front-end", "front end", "фронтенд", "фронт-энд", "фронт-енд")),
    ("backend", ("backend", "back-end", "back end", "бэкенд", "бекенд")),
    ("fullstack", ("fullstack", "full-stack", "full stack", "фулстек", "фуллстек", "фулл-стек")),
    ("mobile", ("mobile", "мобайл", "мобильн", "ios", "android")),
    ("qa", ("qa", "тестировщ", "тестиров")),
    ("devops", ("devops", "девопс")),
    ("data", ("data engineer", "data science", "дата-инженер", "аналитик данных")),
    ("design", ("designer", "дизайнер", "ux/ui", "ui/ux", "ux ui")),
    ("python", ("python", "питон")),
    ("javascript", ("javascript",)),
    ("typescript", ("typescript",)),
    ("java", ("java",)),
    ("golang", ("golang",)),
    ("react", ("react",)),
    ("vue", ("vue",)),
    ("angular", ("angular",)),
    ("nodejs", ("node.js", "nodejs", "node js")),
    ("php", ("php",)),
    ("c++", ("c++",)),
    ("c#", ("c#", "csharp", "c sharp")),
    ("ruby", ("ruby",)),
    ("kotlin", ("kotlin",)),
    ("swift", ("swift",)),
    ("django", ("django",)),
    ("spring", ("spring",)),
    ("docker", ("docker",)),
    ("kubernetes", ("kubernetes", "k8s")),
    ("sql", ("sql", "postgres", "postgresql")),
)

_LOCATION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("Москва", re.compile(r"\b(?:москв\w*|moscow)\b", re.IGNORECASE)),
    ("Санкт-Петербург", re.compile(r"\b(?:санкт[-\s]?петербург\w*|питер|spb|st\.?\s*petersburg)\b", re.IGNORECASE)),
    ("Казань", re.compile(r"\bказан\w*\b", re.IGNORECASE)),
    ("Новосибирск", re.compile(r"\bновосибирск\w*\b", re.IGNORECASE)),
    ("Екатеринбург", re.compile(r"\bекатеринбург\w*\b", re.IGNORECASE)),
    ("Нижний Новгород", re.compile(r"\bнижний\s+новгород\b", re.IGNORECASE)),
    ("Самара", re.compile(r"\bсамар\w*\b", re.IGNORECASE)),
    ("Ростов-на-Дону", re.compile(r"\bростов\w*\b", re.IGNORECASE)),
    ("Уфа", re.compile(r"\bуфа\b", re.IGNORECASE)),
    ("Красноярск", re.compile(r"\bкрасноярск\w*\b", re.IGNORECASE)),
    ("Воронеж", re.compile(r"\bворонеж\w*\b", re.IGNORECASE)),
    ("Краснодар", re.compile(r"\bкраснодар\w*\b", re.IGNORECASE)),
    ("Сочи", re.compile(r"\bсочи\b", re.IGNORECASE)),
    ("Тюмень", re.compile(r"\bтюмен\w*\b", re.IGNORECASE)),
    ("Челябинск", re.compile(r"\bчелябинск\w*\b", re.IGNORECASE)),
    ("Омск", re.compile(r"\bомск\b", re.IGNORECASE)),
    ("Томск", re.compile(r"\bтомск\b", re.IGNORECASE)),
    ("Владивосток", re.compile(r"\bвладивосток\w*\b", re.IGNORECASE)),
    ("Пермь", re.compile(r"\bперм\w*\b", re.IGNORECASE)),
    ("Волгоград", re.compile(r"\bволгоград\w*\b", re.IGNORECASE)),
    ("Саратов", re.compile(r"\bсаратов\w*\b", re.IGNORECASE)),
    ("Удалённо", re.compile(r"\b(?:удал[её]нн\w*|удал[её]нк\w*|дистанционн\w*|remote)\b", re.IGNORECASE)),
)


def utcnow() -> datetime:
    return datetime.now(UTC)


class RussiaVacancySearchAdapter(SourceAdapter):
    name = "Russia Internet Search"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def fetch(self) -> list[Vacancy]:
        queries = _search_queries(self.settings.russia_search_query)
        wanted = max(self.settings.russia_search_results_wanted, 0)
        if wanted <= 0 or not queries:
            return []
        providers = self.settings.russia_search_providers
        vacancies: list[Vacancy] = []
        seen_urls: set[str] = set()
        challenged_providers: set[str] = set()
        failed_providers: set[str] = set()
        attempted_providers: set[str] = set()

        async with source_session(headers=BROWSER_HEADERS) as session:
            for query in queries:
                if len(vacancies) >= wanted:
                    break
                for provider in providers:
                    if len(vacancies) >= wanted:
                        break
                    attempted_providers.add(provider)
                    try:
                        if provider == "bing_rss":
                            results = _rss_results(await _fetch_bing_rss(session, query))
                        else:
                            html = await _fetch_search_html(session, provider, query)
                            if _looks_like_search_challenge(html):
                                challenged_providers.add(provider)
                                continue
                            results = _search_html_results(BeautifulSoup(html or "", "html.parser"))
                        for result in results:
                            if len(vacancies) >= wanted:
                                break
                            vacancy = _result_to_vacancy(result, seen_urls)
                            if vacancy is not None:
                                vacancies.append(vacancy)
                    except Exception as exc:
                        # One blocked or failing provider must not kill the whole
                        # polling cycle; the remaining providers still run.
                        failed_providers.add(provider)
                        logger.warning("%s Russia web search fetch failed: %s", provider, type(exc).__name__)

        if not vacancies and attempted_providers:
            if challenged_providers | failed_providers == attempted_providers:
                details = []
                if challenged_providers:
                    details.append("anti-bot challenges: " + ", ".join(sorted(challenged_providers)))
                if failed_providers:
                    details.append("request failures: " + ", ".join(sorted(failed_providers)))
                raise RuntimeError(
                    "Public web search returned no usable results (" + "; ".join(details) + ")."
                )

        vacancies.sort(key=lambda vacancy: _domain_hint_rank(vacancy.url or ""))
        return filter_fresh_vacancies(
            vacancies,
            max_age_hours=self.settings.source_max_age_hours,
            current_time=utcnow(),
            require_published_at=False,
        )


def _search_queries(raw_query: str) -> tuple[str, ...]:
    return tuple(query.strip() for query in raw_query.split("||") if query.strip())


def _rss_results(rss: str) -> list[SearchHtmlResult]:
    if not (rss or "").strip():
        return []
    try:
        root = ElementTree.fromstring(rss)
    except ElementTree.ParseError:
        return []

    results: list[SearchHtmlResult] = []
    for item in root.findall(".//item"):
        results.append(
            SearchHtmlResult(
                title=_xml_child_text(item, "title"),
                link=_xml_child_text(item, "link"),
                snippet=html_to_text(_xml_child_text(item, "description")),
                date_text=_xml_child_text(item, "pubDate"),
            )
        )
    return results


def _result_to_vacancy(result: SearchHtmlResult, seen_urls: set[str] | None = None) -> Vacancy | None:
    link = _normalize_result_url(result.link or "")
    if not _is_acceptable_url(link):
        return None
    seen = seen_urls if seen_urls is not None else set()
    if link in seen:
        return None

    title = _clean_search_title(result.title)
    snippet = (result.snippet or "").strip()
    if not title or not snippet or _is_spam_title(title):
        return None

    seen.add(link)
    raw_text = f"{title} {snippet}"
    return Vacancy(
        title=title,
        description=snippet,
        source=RussiaVacancySearchAdapter.name,
        url=link,
        location=_location_from_text(raw_text),
        stack=_stack_from_text(raw_text),
        published_at=_published_at(result.date_text, utcnow()),
        raw_text=raw_text,
    )


def _published_at(date_text: str, current_time: datetime) -> datetime | None:
    parsed = parse_source_datetime(date_text)
    if parsed is not None:
        return parsed
    return parse_relative_source_datetime(date_text, current_time=current_time)


def _is_acceptable_url(url: str) -> bool:
    try:
        parts = urlsplit(url)
    except ValueError:
        return False
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        return False
    hostname = (parts.hostname or "").lower()
    if not hostname:
        return False
    for domain in _SEARCH_ENGINE_DOMAINS + _LINKEDIN_DOMAINS:
        if hostname == domain or hostname.endswith("." + domain):
            return False
    return True


def _url_hostname(url: str) -> str:
    try:
        return (urlsplit(url).hostname or "").lower()
    except ValueError:
        return ""


def _domain_hint_rank(url: str) -> int:
    """Priority order from ``RU_JOB_DOMAIN_HINTS``; unknown domains go last.

    Hints are an ordering preference for results, never a domain filter.
    """

    hostname = _url_hostname(url)
    if not hostname:
        return len(RU_JOB_DOMAIN_HINTS)
    for index, hint in enumerate(RU_JOB_DOMAIN_HINTS):
        domain = hint.split("/", 1)[0].lower()
        if domain and (hostname == domain or hostname.endswith("." + domain)):
            return index
    return len(RU_JOB_DOMAIN_HINTS)


def _clean_search_title(title: str) -> str:
    value = (title or "").replace("\xa0", " ")
    value = _TITLE_PREFIX_PATTERN.sub("", value)
    value = _TITLE_SUFFIX_PATTERN.sub("", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip(" |–—·:-()")


def _is_spam_title(title: str) -> bool:
    lower = title.lower()
    if len(lower) < 3:
        return True
    return any(marker in lower for marker in _SPAM_MARKERS)


def _stack_from_text(text: str) -> tuple[str, ...]:
    lower = " ".join((text or "").lower().replace("\xa0", " ").split())
    labels: list[str] = []
    for label, markers in _STACK_MARKERS:
        if any(marker in lower for marker in markers):
            labels.append(label)
    if "java" in labels and "javascript" in labels:
        labels = [label for label in labels if label != "java"]
    return tuple(labels)


def _location_from_text(text: str) -> str | None:
    lower = " ".join((text or "").lower().replace("\xa0", " ").split())
    for label, pattern in _LOCATION_PATTERNS:
        if pattern.search(lower):
            return label
    return None