from __future__ import annotations

import asyncio
import json
import logging
import urllib.request
from urllib.error import HTTPError

from .config import Settings
from .models import VacancyFilter

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"
VARIABLE_SPECIALTIES = "VACANCY_FILTER_SPECIALTIES"
VARIABLE_GRADES = "VACANCY_FILTER_GRADES"


def _call_api(method: str, url: str, token: str, payload: dict) -> tuple[int, str]:
    """One GitHub REST call; returns (status_code, body). Never logs credentials."""
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
            "User-Agent": "tg-vacancy-bot",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return response.status, response.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        return exc.code, error_body
    except Exception as exc:
        return 0, str(exc)


def _set_repository_variable(
    owner: str,
    repo: str,
    token: str,
    name: str,
    value: str,
) -> tuple[bool, str]:
    base_url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/actions/variables"
    status, _body = _call_api("PATCH", f"{base_url}/{name}", token, {"name": name, "value": value})
    if status == 404:
        status, _body = _call_api("POST", base_url, token, {"name": name, "value": value})
    if 200 <= status < 300:
        return True, f"synced GitHub variable {name}={value}"
    return False, f"failed to sync GitHub variable {name} (HTTP {status})"


def sync_vacancy_filter_to_github_sync(
    vacancy_filter: VacancyFilter,
    settings: Settings,
) -> tuple[bool, str]:
    token = settings.github_filter_sync_token.strip()
    repository = settings.github_repository.strip().strip("/")
    if not token or not repository or "/" not in repository:
        return False, "skipped: GITHUB_FILTER_SYNC_TOKEN and GITHUB_REPOSITORY are not configured"

    owner, repo = repository.split("/", 1)
    repo = repo.removesuffix(".git").strip()
    if not owner or not repo:
        return False, "skipped: GITHUB_REPOSITORY must look like owner/repo"

    values = {
        VARIABLE_SPECIALTIES: ",".join(vacancy_filter.specialties),
        VARIABLE_GRADES: ",".join(vacancy_filter.grades),
    }
    results: list[str] = []
    ok = True
    for name, value in values.items():
        success, message = _set_repository_variable(owner, repo, token, name, value)
        ok = ok and success
        if not success:
            logger.warning("GitHub filter sync: %s", message)
        results.append(message)
    return ok, "; ".join(results)


async def sync_vacancy_filter_to_github(
    vacancy_filter: VacancyFilter,
    settings: Settings,
) -> tuple[bool, str]:
    return await asyncio.to_thread(sync_vacancy_filter_to_github_sync, vacancy_filter, settings)