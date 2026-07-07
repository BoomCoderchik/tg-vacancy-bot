from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal


ResultType = Literal["vacancy", "linkedin_user_post"]


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
