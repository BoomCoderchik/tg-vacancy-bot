from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal


ResultType = Literal["vacancy"]
ApplicationStatus = Literal[
    "created", "queued", "loading", "submitting", "parsed", "profile_missing", "unsupported_site", "filled",
    "manual_required", "awaiting_confirmation", "submitted", "failed", "cancelled",
]


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
            return self.url.strip().lower()
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
