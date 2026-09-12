from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import subprocess
import urllib.request
from urllib.error import HTTPError

from .config import Settings
from .models import VacancyFilter

logger = logging.getLogger(__name__)

GITHUB_API_BASE = "https://api.github.com"
VARIABLE_SPECIALTIES = "VACANCY_FILTER_SPECIALTIES"
VARIABLE_GRADES = "VACANCY_FILTER_GRADES"
_GITHUB_HOST = "github.com"


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


def _detect_repository_from_git(workdir: str | os.PathLike | None = None) -> str | None:
    """Read ``owner/repo`` from ``git remote get-url origin`` when available."""
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            timeout=10,
            cwd=workdir or os.getcwd(),
        )
        raw = (result.stdout or "").strip()
    except Exception:
        return None
    if "github.com" not in raw.lower():
        return None
    after = raw.split("://", 1)[1] if "://" in raw else raw
    if "@" in after:
        after = after.rsplit("@", 1)[1]
    if after.lower().startswith(_GITHUB_HOST + "/"):
        path = after[len(_GITHUB_HOST):].strip("/")
    elif after.lower().startswith(_GITHUB_HOST + ":"):
        path = after[len(_GITHUB_HOST):].strip().lstrip(":").strip()
    else:
        return None
    path = path.removesuffix(".git").strip("/")
    if "/" not in path:
        return None
    return path


def _run_gh(owner: str, repo: str, name: str, value: str) -> tuple[bool, str]:
    """Run ``gh variable set`` using the session's GitHub authentication.

    The ``GH_TOKEN``/``GITHUB_TOKEN`` environment variables are cleared so an
    unrelated or stale env token cannot shadow the authenticated CLI session.
    """
    args = ["gh", "variable", "set", name, "--repo", f"{owner}/{repo}", "--body", value]
    env = dict(os.environ)
    env["GH_TOKEN"] = ""
    env["GITHUB_TOKEN"] = ""
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )
    except FileNotFoundError:
        return False, "gh CLI is not installed"
    except subprocess.TimeoutExpired:
        return False, f"gh variable set {name} timed out"
    detail = ((result.stderr or "").strip() or (result.stdout or "").strip())[:300]
    if result.returncode == 0:
        return True, f"synced GitHub variable {name}={value}"
    return False, f"failed to run gh variable set {name} (exit {result.returncode}): {detail}"


def _gh_available() -> bool:
    return shutil.which("gh") is not None


def sync_vacancy_filter_to_github_sync(
    vacancy_filter: VacancyFilter,
    settings: Settings,
    workdir: str | os.PathLike | None = None,
) -> tuple[bool, str]:
    repository = settings.github_repository.strip().strip("/")
    if "/" not in repository:
        repository = _detect_repository_from_git(workdir) or ""
    if "/" not in repository:
        return False, (
            "skipped: no GitHub repository detected - set GITHUB_REPOSITORY "
            "or point the git origin at github.com"
        )

    owner, repo = repository.split("/", 1)
    repo = repo.removesuffix(".git").strip()
    if not owner or not repo:
        return False, "skipped: GitHub repository must look like owner/repo"

    values = {
        VARIABLE_SPECIALTIES: ",".join(vacancy_filter.specialties),
        VARIABLE_GRADES: ",".join(vacancy_filter.grades),
    }
    token = settings.github_filter_sync_token.strip()

    results: list[str] = []
    ok = True
    for name, value in values.items():
        if token:
            success, message = _set_repository_variable(owner, repo, token, name, value)
        elif _gh_available():
            success, message = _run_gh(owner, repo, name, value)
        else:
            return False, (
                "skipped: no GITHUB_FILTER_SYNC_TOKEN and no gh CLI available "
                "to update GitHub variables"
            )
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