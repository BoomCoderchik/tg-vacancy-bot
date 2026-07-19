from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import aiohttp

from tg_vacancy_bot.config import Settings
from tg_vacancy_bot.models import Vacancy
from tg_vacancy_bot.sources.base import SourceAdapter, source_session
from tg_vacancy_bot.sources.dates import parse_source_datetime
from tg_vacancy_bot.sources.freshness import filter_fresh_vacancies


SERPAPI_SEARCH_URL = "https://serpapi.com/search.json"
SERPER_SEARCH_URL = "https://google.serper.dev/search"
SERPER_MAX_RESULTS_PER_REQUEST = 10
POST_URL_MARKERS = ("linkedin.com/posts/", "linkedin.com/feed/update/")
POST_PATH_PREFIXES = ("/posts/", "/feed/update/")
ACTIVITY_ID_PATTERN = re.compile(r"activity-(\d{15,20})(?:[-/?#]|$)", re.IGNORECASE)
HASHTAG_PATTERN = re.compile(r"(?<!\w)#[\w.+-]+", re.UNICODE)
ROLE_TERM_PATTERN = re.compile(
    r"\b(?P<role>"
    r"(?:(?:junior|middle|mid-level|mid|senior|lead|staff|principal|trainee|intern)\s+)?"
    r"(?:front[-\s]?end|frontend|back[-\s]?end|backend|full[-\s]?stack|full\s+stack|software|cloud|"
    r"python|java|golang|go|node(?:\.js)?|react|vue|angular|typescript|javascript|mobile|ios|android|"
    r"ml|ai|llm|machine\s+learning|data)\s+"
    r"(?:developer|engineer|architect|programmer)"
    r"(?:\s*\([^)]+\))?"
    r")\b",
    re.IGNORECASE,
)
ROLE_NOUN_FIRST_PATTERN = re.compile(
    r"\b(?P<role>"
    r"(?:(?:junior|middle|mid-level|mid|senior|lead|staff|principal|trainee|intern)\s+)?"
    r"(?:developer|engineer|architect|programmer)\s+"
    r"(?:front[-\s]?end|frontend|back[-\s]?end|backend|full[-\s]?stack|full\s+stack|software|cloud|"
    r"python|java|golang|go|node(?:\.js)?|react|vue|angular|typescript|javascript|mobile|ios|android|"
    r"ml|ai|llm|machine\s+learning|data)"
    r"(?:\s*\([^)]+\))?"
    r")\b",
    re.IGNORECASE,
)
RU_ROLE_PATTERN = re.compile(
    r"(?P<role>"
    r"(?:(?:junior|middle|senior|lead|джуниор|мидл|сеньор|ведущий|стаж[её]р)\s+)?"
    r"(?:(?:front[-\s]?end|frontend|back[-\s]?end|backend|full[-\s]?stack|python|java|go|react|"
    r"vue|angular|typescript|javascript|ml|ai|llm)\s*[- ]*)?"
    r"(?:разработчик|инженер|программист)"
    r"(?:\s+(?:front[-\s]?end|frontend|back[-\s]?end|backend|full[-\s]?stack|python|java|go|react|"
    r"vue|angular|typescript|javascript|ml|ai|llm))?"
    r"(?:\s*\([^)]+\))?"
    r")",
    re.IGNORECASE,
)


def utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class LinkedInPostCandidate:
    """Raw search discovery result that has not passed vacancy policy yet."""

    url: str
    search_title: str
    snippet: str
    date_text: str
    provider: str
    query: str
    family: str = ""
    language: str = ""
    position: int = 0


class LinkedInSearchProviderError(RuntimeError):
    """Safe provider failure that preserves only a response status code."""

    def __init__(self, status_code: int | None = None, failure_type: str = "") -> None:
        self.status_code = status_code
        self.failure_type = failure_type
        detail = f" (HTTP {status_code})" if status_code is not None else ""
        super().__init__(f"LinkedIn search provider request failed{detail}")


class LinkedInPostSearchAdapter(SourceAdapter):
    name = "LinkedIn Hiring Posts"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def fetch(self) -> list[Vacancy]:
        candidates = await self.discover()
        vacancies = [
            vacancy
            for candidate in candidates
            if (vacancy := _candidate_to_vacancy(candidate)) is not None
        ]
        return _filter_recent_linkedin_posts(vacancies, self.settings.linkedin_post_max_age_hours)

    async def discover(self, *, limit: int | None = None) -> list[LinkedInPostCandidate]:
        wanted = max(
            self.settings.linkedin_post_search_results_wanted if limit is None else limit,
            0,
        )
        candidates: list[LinkedInPostCandidate] = []
        seen_urls: set[str] = set()
        async with source_session() as session:
            for query in _search_queries(self.settings.linkedin_post_search_query):
                if len(candidates) >= wanted:
                    break
                params = {
                    "engine": "google",
                    "api_key": self.settings.serpapi_api_key,
                    "q": query,
                    "num": wanted,
                    "hl": "ru",
                    # Google only supports coarse date windows. The common
                    # freshness filter below still enforces the exact
                    # configured five-day (or shorter) limit.
                    "tbs": _google_recency_filter(self.settings.linkedin_post_max_age_hours),
                }
                payload = await _get_search_payload(session, SERPAPI_SEARCH_URL, params=params)

                for result in payload.get("organic_results", []):
                    if not isinstance(result, Mapping):
                        continue
                    candidate = _result_to_candidate(result, provider=self.name, query=query)
                    if candidate is None or candidate.url in seen_urls:
                        continue
                    seen_urls.add(candidate.url)
                    candidates.append(candidate)
                    if len(candidates) >= wanted:
                        break
        return candidates


class LinkedInPostSerperAdapter(SourceAdapter):
    name = "LinkedIn Hiring Posts (Serper)"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def fetch(self) -> list[Vacancy]:
        candidates = await self.discover()
        vacancies = [
            vacancy
            for candidate in candidates
            if (vacancy := _candidate_to_vacancy(candidate)) is not None
        ]
        return _filter_recent_linkedin_posts(vacancies, self.settings.linkedin_post_max_age_hours)

    async def discover(self, *, limit: int | None = None) -> list[LinkedInPostCandidate]:
        wanted = max(
            self.settings.linkedin_post_search_results_wanted if limit is None else limit,
            0,
        )
        headers = {"X-API-KEY": self.settings.serper_api_key, "Content-Type": "application/json"}
        candidates: list[LinkedInPostCandidate] = []
        seen_urls: set[str] = set()
        async with source_session(headers=headers) as session:
            for query in _search_queries(self.settings.linkedin_post_search_query):
                page = 1
                while len(candidates) < wanted:
                    request_limit = min(SERPER_MAX_RESULTS_PER_REQUEST, wanted - len(candidates))
                    payload = {
                        "q": query,
                        "num": request_limit,
                        "hl": "ru",
                        "tbs": _google_recency_filter(self.settings.linkedin_post_max_age_hours),
                    }
                    if page > 1:
                        payload["page"] = page
                    response_payload = await _post_search_payload(
                        session,
                        SERPER_SEARCH_URL,
                        payload=payload,
                    )

                    results = response_payload.get("organic", [])
                    if not isinstance(results, list):
                        break
                    for result in results:
                        if not isinstance(result, Mapping):
                            continue
                        candidate = _result_to_candidate(
                            result,
                            provider=self.name,
                            query=query,
                        )
                        if candidate is None or candidate.url in seen_urls:
                            continue
                        seen_urls.add(candidate.url)
                        candidates.append(candidate)
                        if len(candidates) >= wanted:
                            break
                    if len(results) < request_limit:
                        break
                    page += 1
        return candidates


def _result_to_vacancy(
    result: Mapping[str, Any],
    *,
    source: str = LinkedInPostSearchAdapter.name,
) -> Vacancy | None:
    candidate = _result_to_candidate(result, provider=source, query="")
    return _candidate_to_vacancy(candidate) if candidate is not None else None


def _result_to_candidate(
    result: Mapping[str, Any],
    *,
    provider: str,
    query: str,
    position: int = 0,
) -> LinkedInPostCandidate | None:
    search_title = _clean_title(_text(result, "title"))
    link = _canonicalize_linkedin_post_url(_text(result, "link"))
    snippet = _text(result, "snippet")
    if not link:
        return None

    return LinkedInPostCandidate(
        url=link,
        search_title=search_title,
        snippet=snippet,
        date_text=_text(result, "date"),
        provider=provider,
        query=query,
        position=max(position, 0),
    )


def _candidate_to_vacancy(candidate: LinkedInPostCandidate) -> Vacancy | None:
    if not candidate.search_title or not candidate.snippet:
        return None
    title = _post_title(candidate.search_title, candidate.snippet)

    return Vacancy(
        title=title,
        description=candidate.snippet,
        source=candidate.provider,
        url=candidate.url,
        location=None,
        stack=_stack_from_text(f"{title} {candidate.snippet} {candidate.search_title}"),
        published_at=_published_at_for_result(candidate.date_text, candidate.url),
        raw_text=f"{title} {candidate.snippet}",
    )


def _filter_recent_linkedin_posts(vacancies: list[Vacancy], max_age_hours: int) -> list[Vacancy]:
    return filter_fresh_vacancies(
        vacancies,
        max_age_hours=max_age_hours,
        current_time=utcnow(),
        require_published_at=True,
    )


def _google_recency_filter(max_age_hours: int) -> str:
    """Return the narrowest supported Google ``tbs=qdr`` time window.

    The caller must still verify every candidate date: Google can only express
    hour/day/week/month/year ranges, while the configured LinkedIn boundary is
    exact and may be as short as a few hours.
    """

    if max_age_hours <= 1:
        return "qdr:h"
    if max_age_hours <= 24:
        return "qdr:d"
    if max_age_hours <= 24 * 7:
        return "qdr:w"
    if max_age_hours <= 24 * 31:
        return "qdr:m"
    return "qdr:y"


def _is_linkedin_post_url(link: str) -> bool:
    lower = link.lower()
    return any(marker in lower for marker in POST_URL_MARKERS)


def _canonicalize_linkedin_post_url(link: str) -> str:
    value = (link or "").strip()
    if not value:
        return ""
    parsed = urlsplit(value)
    hostname = (parsed.hostname or "").lower()
    if parsed.scheme not in {"http", "https"} or not (
        hostname == "linkedin.com" or hostname.endswith(".linkedin.com")
    ):
        return ""
    path = parsed.path.rstrip("/")
    if not any(path.startswith(prefix) and len(path) > len(prefix) for prefix in POST_PATH_PREFIXES):
        return ""
    canonical = urlunsplit(("https", "www.linkedin.com", path, "", ""))
    return canonical


async def _get_search_payload(session, url: str, *, params: Mapping[str, Any]) -> Mapping[str, Any]:
    try:
        async with session.get(url, params=params) as response:
            response.raise_for_status()
            payload = await response.json()
    except aiohttp.ClientResponseError as exc:
        raise LinkedInSearchProviderError(exc.status) from None
    except aiohttp.ClientError as exc:
        raise LinkedInSearchProviderError(failure_type=type(exc).__name__) from None
    return payload if isinstance(payload, Mapping) else {}


async def _post_search_payload(session, url: str, *, payload: Mapping[str, Any]) -> Mapping[str, Any]:
    try:
        async with session.post(url, json=payload) as response:
            response.raise_for_status()
            response_payload = await response.json()
    except aiohttp.ClientResponseError as exc:
        raise LinkedInSearchProviderError(exc.status) from None
    except aiohttp.ClientError as exc:
        raise LinkedInSearchProviderError(failure_type=type(exc).__name__) from None
    return response_payload if isinstance(response_payload, Mapping) else {}


def _post_title(search_title: str, snippet: str) -> str:
    role = _extract_role_title(f"{search_title}. {snippet}")
    if role:
        return role
    without_hashtags = _strip_hashtags(search_title)
    return without_hashtags or search_title


def _extract_role_title(text: str) -> str:
    normalized = " ".join((text or "").replace("\xa0", " ").split())
    for pattern in (ROLE_TERM_PATTERN, ROLE_NOUN_FIRST_PATTERN, RU_ROLE_PATTERN):
        match = pattern.search(normalized)
        if match:
            return _normalize_role(match.group("role"))
    return ""


def _normalize_role(role: str) -> str:
    role = role.strip(" .,:;!?)(")
    role = re.sub(r"\s+", " ", role)
    role = re.sub(r"\s+-\s+", "-", role)
    return role[:1].upper() + role[1:] if role else ""


def _strip_hashtags(title: str) -> str:
    cleaned = HASHTAG_PATTERN.sub("", title)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip(" -|.,")


def _search_queries(raw_query: str) -> tuple[str, ...]:
    return tuple(query.strip() for query in raw_query.split("||") if query.strip())


def _clean_title(title: str) -> str:
    for suffix in (" | LinkedIn", " в LinkedIn", " on LinkedIn", " - LinkedIn"):
        if title.endswith(suffix):
            return title[: -len(suffix)].strip()
    return title


def _stack_from_text(text: str) -> tuple[str, ...]:
    lower = text.lower()
    pairs = (
        ("LinkedIn post", "linkedin"),
        ("frontend", "frontend"),
        ("frontend", "front-end"),
        ("backend", "backend"),
        ("fullstack", "fullstack"),
        ("fullstack", "full-stack"),
        ("designer", "designer"),
        ("AI", "ai engineer"),
        ("ML", "ml engineer"),
        ("LLM", "llm"),
        ("Angular", "angular"),
        ("React", "react"),
        ("TypeScript", "typescript"),
        ("JavaScript", "javascript"),
        ("Python", "python"),
        ("REST API", "rest api"),
    )
    values = ["LinkedIn post"]
    for label, marker in pairs:
        if marker in lower and label not in values:
            values.append(label)
    return tuple(values)


def _text(result: Mapping[str, Any], key: str) -> str:
    value = result.get(key)
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() in {"nan", "none", "nat"} else text


def _parse_search_date(value: str) -> datetime | None:
    parsed = parse_source_datetime(value)
    if parsed is not None or not value:
        return parsed
    for fmt in ("%b %d, %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=UTC)
        except ValueError:
            pass
    return None


def _published_at_for_result(date_text: str, link: str) -> datetime | None:
    parsed = _parse_search_date(date_text)
    if parsed is not None:
        return parsed
    return _published_at_from_activity_id(link)


def _published_at_from_activity_id(link: str) -> datetime | None:
    match = ACTIVITY_ID_PATTERN.search(link)
    if not match:
        return None
    try:
        timestamp_ms = int(match.group(1)) >> 22
        return datetime.fromtimestamp(timestamp_ms / 1000, tz=UTC)
    except (ValueError, OSError, OverflowError):
        return None
