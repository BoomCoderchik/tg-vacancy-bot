from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal
from urllib.parse import urlsplit, urlunsplit


ResultType = Literal["vacancy"]
ApplicationStatus = Literal[
    "created", "queued", "loading", "submitting", "parsed", "profile_missing", "unsupported_site", "filled",
    "manual_required", "awaiting_confirmation", "submitted", "failed", "cancelled",
]

_TRACKING_QUERY_PARAMS = frozenset({"fbclid", "gclid", "mc_cid", "mc_eid", "igshid", "si"})


def canonical_identity_url(url: str) -> str:
    cleaned = url.strip()
    try:
        parts = urlsplit(cleaned)
    except ValueError:
        return cleaned.lower()
    if not parts.scheme or not parts.netloc:
        return cleaned.lower()
    userinfo, at_sign, host_port = parts.netloc.rpartition("@")
    netloc = f"{userinfo}{at_sign}{host_port.lower()}" if at_sign else host_port.lower()
    path = parts.path
    if len(path) > 1 and path.endswith("/"):
        path = path[:-1]
    kept_params = []
    for chunk in parts.query.split("&"):
        if not chunk:
            continue
        name = chunk.split("=", 1)[0].lower()
        if not name.startswith("utm_") and name not in _TRACKING_QUERY_PARAMS:
            kept_params.append(chunk)
    return urlunsplit((parts.scheme, netloc, path, "&".join(kept_params), ""))


@dataclass(frozen=True)
class Vacancy:
    title: str
    description: str
    source: str
    result_type: ResultType = "vacancy"
    url: str | None = None
    location: str | None = None
    company: str | None = None
    role: str | None = None
    stack: tuple[str, ...] = field(default_factory=tuple)
    salary: str | None = None
    published_at: datetime | None = None
    detected_at: datetime | None = None
    raw_text: str = ""

    @property
    def identity_source(self) -> str:
        if self.url:
            return canonical_identity_url(self.url.strip())
        parts = [self.title, self.company or "", self.location or "", self.description[:240]]
        return "|".join(part.strip().lower() for part in parts if part)


@dataclass(frozen=True)
class OperatorProfile:
    """Private application data owned by one authorized Telegram operator."""

    operator_user_id: int
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    desired_salary: str | None = None
    location: str | None = None
    work_format: str | None = None
    employment_type: str | None = None
    extra_fields: dict[str, str] = field(default_factory=dict)
    resume_original_name: str | None = None
    resume_stored_name: str | None = None
    resume_telegram_file_id: str | None = None
    resume_text: str | None = None


@dataclass(frozen=True)
class Application:
    application_id: str
    operator_user_id: int
    vacancy_fingerprint: str
    vacancy_url: str | None
    site: str | None
    status: ApplicationStatus
    error_description: str | None = None
