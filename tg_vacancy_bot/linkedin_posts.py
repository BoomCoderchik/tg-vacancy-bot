from __future__ import annotations

import re
from datetime import UTC, datetime
from urllib.parse import urlparse

from .models import Vacancy
from .parser import extract_urls


LINKEDIN_USER_POST_SOURCE = "LinkedIn user posts"

HIRING_INTENT_PATTERNS = [
    re.compile(r"\b(?:we(?:'| a)?re|we are|i am|i'm|im)\s+hiring\b", re.IGNORECASE),
    re.compile(r"\bhiring\s+(?:a|an|for|remote|senior|middle|junior)?\b", re.IGNORECASE),
    re.compile(r"\blooking\s+for\s+(?:a|an)?\s*", re.IGNORECASE),
    re.compile(r"\bneed\s+(?:a|an)?\s*", re.IGNORECASE),
    re.compile(r"\bjoin\s+our\s+team\b", re.IGNORECASE),
    re.compile(r"\bищ(?:ем|у)\b", re.IGNORECASE),
    re.compile(r"\bнуж(?:ен|на|ны)\b", re.IGNORECASE),
]

NEGATIVE_POST_PATTERNS = [
    re.compile(r"\blooking\s+for\s+(?:a\s+)?job\b", re.IGNORECASE),
    re.compile(r"\bopen\s+to\s+work\b", re.IGNORECASE),
    re.compile(r"\bmy\s+resume\b", re.IGNORECASE),
    re.compile(r"\bcv\b", re.IGNORECASE),
    re.compile(r"\bcourse\b", re.IGNORECASE),
    re.compile(r"\bbootcamp\b", re.IGNORECASE),
    re.compile(r"\bwebinar\b", re.IGNORECASE),
    re.compile(r"\bnews\b", re.IGNORECASE),
    re.compile(r"\b(?:thoughts|article|guide|tips|post)\s+on\s+hiring\b", re.IGNORECASE),
    re.compile(r"\bhow\s+to\s+hire\b", re.IGNORECASE),
    re.compile(r"\bрезюме\b", re.IGNORECASE),
    re.compile(r"\bищу\s+работу\b", re.IGNORECASE),
    re.compile(r"\bкурс\b", re.IGNORECASE),
    re.compile(r"\bобучени[ея]\b", re.IGNORECASE),
]

ROLE_PATTERNS = [
    ("React developer", re.compile(r"\breact(?:\.js)?\s+(?:developer|engineer)\b", re.IGNORECASE)),
    ("Vue developer", re.compile(r"\bvue(?:\.js)?\s+(?:developer|engineer)\b", re.IGNORECASE)),
    ("Angular developer", re.compile(r"\bangular\s+(?:developer|engineer)\b", re.IGNORECASE)),
    ("Node.js developer", re.compile(r"\bnode(?:\.js)?\s+(?:developer|engineer)\b", re.IGNORECASE)),
    ("Python developer", re.compile(r"\bpython\s+(?:developer|engineer)\b", re.IGNORECASE)),
    ("PHP developer", re.compile(r"\bphp\s+(?:developer|engineer)\b", re.IGNORECASE)),
    ("Java developer", re.compile(r"\bjava\s+(?:developer|engineer)\b", re.IGNORECASE)),
    ("frontend developer", re.compile(r"\bfront[- ]?end\s+(?:developer|engineer)\b", re.IGNORECASE)),
    ("backend engineer", re.compile(r"\bback[- ]?end\s+(?:developer|engineer)\b", re.IGNORECASE)),
    ("fullstack developer", re.compile(r"\bfull[- ]?stack\s+(?:developer|engineer)\b", re.IGNORECASE)),
    ("mobile developer", re.compile(r"\bmobile\s+(?:developer|engineer)\b", re.IGNORECASE)),
    ("UI/UX designer", re.compile(r"\bui/ux\s+designer\b|\bux/ui\s+designer\b", re.IGNORECASE)),
    ("product designer", re.compile(r"\bproduct\s+designer\b", re.IGNORECASE)),
    ("graphic designer", re.compile(r"\bgraphic\s+designer\b", re.IGNORECASE)),
    ("developer", re.compile(r"\bdevelopers?\b|\bengineers?\b|\bразработчик(?:а|ов)?\b", re.IGNORECASE)),
    ("designer", re.compile(r"\bdesigners?\b|\bдизайнер(?:а|ов)?\b", re.IGNORECASE)),
]


def classify_linkedin_user_post(text: str) -> str | None:
    normalized = " ".join((text or "").split())
    if not normalized:
        return None
    if any(pattern.search(normalized) for pattern in NEGATIVE_POST_PATTERNS):
        return None
    if not any(pattern.search(normalized) for pattern in HIRING_INTENT_PATTERNS):
        return None
    for role, pattern in ROLE_PATTERNS:
        if pattern.search(normalized):
            return role
    return None


def build_linkedin_user_post_vacancy(
    record: dict[str, object],
    *,
    now: datetime | None = None,
    max_age_hours: int | None = None,
) -> Vacancy | None:
    text = _first_text(record, "text", "content", "body", "summary")
    url = _first_text(record, "url", "link", "post_url", "postUrl")
    if not text or not url or not _is_linkedin_url(url):
        return None

    role = classify_linkedin_user_post(text)
    if not role:
        return None

    published_at = _parse_datetime(
        record.get("published_at")
        or record.get("publishedAt")
        or record.get("created_at")
        or record.get("createdAt")
        or record.get("date")
    )
    if _is_stale(published_at, now=now, max_age_hours=max_age_hours):
        return None
    detected_at = now or datetime.now(UTC)

    return Vacancy(
        title=_title(record, text),
        description=text,
        source=LINKEDIN_USER_POST_SOURCE,
        result_type="linkedin_user_post",
        url=url,
        company=_first_text(record, "author", "company", "profile_name", "profileName"),
        role=role,
        published_at=published_at,
        detected_at=detected_at,
        raw_text=text,
    )


def build_linkedin_user_post_vacancy_from_text(
    text: str,
    *,
    now: datetime | None = None,
    max_age_hours: int | None = None,
) -> Vacancy | None:
    if _looks_like_structured_vacancy_text(text):
        return None
    linkedin_url = next((url for url in extract_urls(text) if _is_linkedin_url(url)), "")
    if not linkedin_url:
        return None
    return build_linkedin_user_post_vacancy(
        {
            "url": linkedin_url,
            "text": text,
        },
        now=now,
        max_age_hours=max_age_hours,
    )


def extract_linkedin_user_post_records(payload: object) -> list[dict[str, object]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("posts", "items", "data", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        return [payload]
    return []


def _looks_like_structured_vacancy_text(text: str) -> bool:
    return bool(
        re.search(
            r"(?im)^\s*(?:location|stack|tech stack|salary|description|company)\s*:",
            text or "",
        )
    )


def _first_text(record: dict[str, object], *keys: str) -> str:
    for key in keys:
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return " ".join(value.split())
    return ""


def _title(record: dict[str, object], text: str) -> str:
    configured_title = _first_text(record, "title", "headline")
    if configured_title:
        return configured_title[:120]
    return text[:117].rstrip() + "..." if len(text) > 120 else text


def _is_linkedin_url(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    return host == "linkedin.com" or host.endswith(".linkedin.com")


def _parse_datetime(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return _to_utc(value)
    if isinstance(value, int | float):
        return _parse_timestamp(value)
    if not isinstance(value, str):
        return None

    text = value.strip()
    if not text:
        return None
    if text.isdigit():
        return _parse_timestamp(int(text))
    normalized = text.removesuffix("Z") + "+00:00" if text.endswith("Z") else text
    try:
        return _to_utc(datetime.fromisoformat(normalized))
    except ValueError:
        return None


def _parse_timestamp(value: int | float) -> datetime | None:
    timestamp = value / 1000 if value > 10_000_000_000 else value
    try:
        return datetime.fromtimestamp(timestamp, tz=UTC)
    except (OSError, OverflowError, ValueError):
        return None


def _to_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _is_stale(
    published_at: datetime | None,
    *,
    now: datetime | None,
    max_age_hours: int | None,
) -> bool:
    if not published_at or not max_age_hours or max_age_hours <= 0:
        return False
    current_time = now or datetime.now(UTC)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=UTC)
    return (current_time - published_at).total_seconds() > max_age_hours * 3600
