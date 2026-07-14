from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from .models import OperatorProfile


ARBEITNOW_DOMAIN = "arbeitnow.com"


@dataclass(frozen=True)
class ArbeitnowApplicationPlan:
    application_url: str
    first_name: str | None
    last_name: str | None
    email: str | None
    phone: str | None
    personal_url: str | None
    cover_letter: str | None
    resume_path: Path | None
    missing_fields: tuple[str, ...]


def is_arbeitnow_url(url: str) -> bool:
    hostname = (urlparse(url).hostname or "").lower()
    return hostname == ARBEITNOW_DOMAIN or hostname.endswith(f".{ARBEITNOW_DOMAIN}")


def build_arbeitnow_application_plan(
    vacancy_url: str, profile: OperatorProfile | None, resume_path: Path | None,
) -> ArbeitnowApplicationPlan:
    """Map the private profile to Arbeitnow's public form without submitting it."""
    if not is_arbeitnow_url(vacancy_url):
        raise ValueError("Arbeitnow adapter received a different domain")

    name_parts = (profile.full_name or "").strip().split() if profile else []
    first_name = name_parts[0] if name_parts else None
    last_name = " ".join(name_parts[1:]) or None
    email = profile.email.strip() if profile and profile.email else None
    phone = profile.phone.strip() if profile and profile.phone else None
    extra_fields = profile.extra_fields if profile else {}
    personal_url = extra_fields.get("personal_url") or extra_fields.get("website")
    cover_letter = extra_fields.get("cover_letter")
    application_url = vacancy_url.rstrip("/")
    if not application_url.endswith("/apply"):
        application_url = f"{application_url}/apply"

    missing = []
    if not first_name or not last_name:
        missing.append("full_name")
    if not email:
        missing.append("email")
    if resume_path is None or not resume_path.is_file():
        missing.append("resume")
    return ArbeitnowApplicationPlan(
        application_url=application_url,
        first_name=first_name,
        last_name=last_name,
        email=email,
        phone=phone,
        personal_url=personal_url,
        cover_letter=cover_letter,
        resume_path=resume_path,
        missing_fields=tuple(missing),
    )
