from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal, Protocol

from bs4 import BeautifulSoup

from tg_vacancy_bot.config import Settings
from tg_vacancy_bot.sources.adapters.linkedin_post_headless import (
    _fetch_bing_rss,
    _fetch_provider_html,
    _rss_post_results,
    _search_html_results,
)
from tg_vacancy_bot.sources.adapters.linkedin_post_scraper import (
    BROWSER_HEADERS,
    _normalize_result_url,
)
from tg_vacancy_bot.sources.adapters.linkedin_post_search import (
    LinkedInPostCandidate,
    LinkedInPostSearchAdapter,
    LinkedInSearchProviderError,
    _canonicalize_linkedin_post_url,
    _published_at_for_result,
)
from tg_vacancy_bot.sources.base import source_session
from tg_vacancy_bot.sources.linkedin_search_profile import (
    fair_query_limits,
    select_cycle_intents,
    select_search_intents,
)


DiagnosticStatus = Literal[
    "no_results",
    "ok",
    "degraded",
    "provider_error",
]
PermissionGateState = Literal["authorized", "not_authorized", "incomplete"]
ProviderStatus = Literal["ok", "degraded", "error"]

_SAFE_ERROR_TYPE = re.compile(r"[^A-Za-z0-9_.]")
MAX_DIAGNOSTIC_RESULTS_PER_PROVIDER = 100


class _DiscoveryProvider(Protocol):
    async def discover(self, *, limit: int | None = None) -> list[LinkedInPostCandidate]: ...


@dataclass(frozen=True, slots=True)
class LinkedInProviderDiagnosticResult:
    """Non-sensitive discovery outcome for one configured search provider."""

    provider: str
    urls: tuple[str, ...] = ()
    error_type: str | None = None
    queries_attempted: int = 0
    query_errors: int = 0
    family_counts: tuple[tuple[str, int], ...] = ()

    @property
    def status(self) -> ProviderStatus:
        if self.queries_attempted and self.query_errors >= self.queries_attempted:
            return "error"
        if self.query_errors:
            return "degraded"
        return "ok"

    @property
    def candidate_count(self) -> int:
        return len(self.urls)


@dataclass(frozen=True, slots=True)
class LinkedInDiagnosticReport:
    """Discovery-only report that deliberately excludes snippets and credentials."""

    status: DiagnosticStatus
    permission_gate: PermissionGateState
    providers: tuple[LinkedInProviderDiagnosticResult, ...]
    urls: tuple[str, ...]
    selected_intents: tuple[str, ...] = ()
    total_profile_intents: int = 0
    fresh_date_hints: int = 0
    stale_date_hints: int = 0
    undated: int = 0

    @property
    def provider_count(self) -> int:
        return len(self.providers)

    @property
    def candidate_count(self) -> int:
        return sum(provider.candidate_count for provider in self.providers)

    @property
    def unique_count(self) -> int:
        return len(self.urls)


async def collect_linkedin_diagnostics(
    settings: Settings,
    limit: int,
) -> LinkedInDiagnosticReport:
    """Run configured discovery providers without browser or publishing side effects.

    With a SerpApi key the keyed provider is exercised; otherwise the same
    free public search providers that power production discovery are probed
    per intent so blockages are visible without any API key.
    """

    current_time = utcnow()
    wanted = min(max(limit, 0), MAX_DIAGNOSTIC_RESULTS_PER_PROVIDER)
    keyed_providers: list[tuple[str, type[_DiscoveryProvider]]] = []
    if settings.serpapi_api_key.strip():
        keyed_providers.append(("serpapi", LinkedInPostSearchAdapter))

    all_intents = select_search_intents(settings.linkedin_post_headless_query)
    selected = select_cycle_intents(
        all_intents,
        max_intents=settings.linkedin_post_search_intents_per_cycle,
        cycle_index=_search_cycle_index(current_time),
    )
    query_limits = fair_query_limits(max(wanted, len(selected)), selected)
    intent_labels = tuple(f"{intent.family}:{intent.language}" for intent in selected)

    permission_gate = _permission_gate(settings)

    provider_results: list[LinkedInProviderDiagnosticResult] = []
    unique_urls: list[str] = []
    seen_urls: set[str] = set()
    published_at_hints: dict[str, datetime | None] = {}

    for provider_name, provider_type in keyed_providers:
        provider_urls: list[str] = []
        provider_seen_urls: set[str] = set()
        family_counts: dict[str, int] = {}
        query_errors = 0
        error_type: str | None = None
        for intent, query_limit in zip(selected, query_limits, strict=True):
            search_settings = settings.model_copy(
                update={
                    "linkedin_post_search_query": intent.query,
                    "linkedin_post_search_results_wanted": query_limit,
                }
            )
            adapter = provider_type(search_settings)
            try:
                candidates = await adapter.discover(limit=query_limit)
            except Exception as exc:
                query_errors += 1
                error_type = error_type or _sanitized_error_type(exc)
                continue
            for candidate in candidates:
                _collect_candidate(
                    candidate,
                    intent_family=intent.family,
                    provider_seen_urls=provider_seen_urls,
                    provider_urls=provider_urls,
                    family_counts=family_counts,
                    seen_urls=seen_urls,
                    unique_urls=unique_urls,
                    published_at_hints=published_at_hints,
                )

        provider_results.append(
            LinkedInProviderDiagnosticResult(
                provider=provider_name,
                urls=tuple(provider_urls),
                error_type=error_type,
                queries_attempted=len(selected),
                query_errors=query_errors,
                family_counts=tuple(family_counts.items()),
            )
        )

    if not keyed_providers and selected:
        provider_results.extend(
            await _free_provider_diagnostics(
                settings,
                selected,
                wanted,
                seen_urls=seen_urls,
                unique_urls=unique_urls,
                published_at_hints=published_at_hints,
            )
        )

    results = tuple(provider_results)
    cutoff = current_time - timedelta(hours=settings.linkedin_post_max_age_hours)
    dated_hints = tuple(value for value in published_at_hints.values() if value is not None)
    return LinkedInDiagnosticReport(
        status=_diagnostic_status(results, unique_urls),
        permission_gate=permission_gate,
        providers=results,
        urls=tuple(unique_urls),
        selected_intents=intent_labels,
        total_profile_intents=len(all_intents),
        fresh_date_hints=sum(value >= cutoff for value in dated_hints),
        stale_date_hints=sum(value < cutoff for value in dated_hints),
        undated=sum(value is None for value in published_at_hints.values()),
    )


def format_linkedin_diagnostics(
    report: LinkedInDiagnosticReport,
    show_limit: int = 5,
) -> str:
    """Format a compact, secret-free discovery report for console output."""

    lines = [
        "LinkedIn diagnostics",
        (
            f"stage=discovery status={report.status} "
            f"permission_gate={report.permission_gate} providers={report.provider_count} "
            f"candidates={report.candidate_count} unique={report.unique_count} "
            f"profile_intents={len(report.selected_intents)}/{report.total_profile_intents} "
            f"date_hints=fresh:{report.fresh_date_hints},stale:{report.stale_date_hints},undated:{report.undated}"
        ),
    ]
    if report.selected_intents:
        lines.append("intents=" + ",".join(report.selected_intents))
    for provider in report.providers:
        line = (
            f"provider={provider.provider} status={provider.status} "
            f"queries={provider.queries_attempted} query_errors={provider.query_errors} "
            f"candidates={provider.candidate_count}"
        )
        if provider.error_type:
            line += f" error_type={provider.error_type}"
        lines.append(line)
        for family, count in provider.family_counts:
            lines.append(f"provider={provider.provider} family={family} candidates={count}")

    visible_limit = max(show_limit, 0)
    for url in report.urls[:visible_limit]:
        lines.append(f"url={url}")
    omitted = report.unique_count - min(report.unique_count, visible_limit)
    if omitted:
        lines.append(f"urls_omitted={omitted}")
    return "\n".join(lines)


def _permission_gate(settings: Settings) -> PermissionGateState:
    authorized = settings.linkedin_headless_access_authorized
    has_reference = bool(settings.linkedin_headless_permission_reference.strip())
    if authorized and has_reference:
        return "authorized"
    if authorized or has_reference:
        return "incomplete"
    return "not_authorized"


def _collect_candidate(
    candidate: LinkedInPostCandidate,
    *,
    intent_family: str,
    provider_seen_urls: set[str],
    provider_urls: list[str],
    family_counts: dict[str, int],
    seen_urls: set[str],
    unique_urls: list[str],
    published_at_hints: dict[str, datetime | None],
) -> None:
    url = str(candidate.url).strip()
    if not url or url in provider_seen_urls:
        return
    provider_seen_urls.add(url)
    provider_urls.append(url)
    family_counts[intent_family] = family_counts.get(intent_family, 0) + 1
    published_at = _published_at_for_result(candidate.date_text, url)
    if url not in seen_urls:
        seen_urls.add(url)
        unique_urls.append(url)
        published_at_hints[url] = published_at
    elif published_at_hints[url] is None and published_at is not None:
        published_at_hints[url] = published_at


async def _free_provider_diagnostics(
    settings: Settings,
    selected,
    wanted: int,
    *,
    seen_urls: set[str],
    unique_urls: list[str],
    published_at_hints: dict[str, datetime | None],
) -> tuple[LinkedInProviderDiagnosticResult, ...]:
    """Probe each free public search provider per intent without a browser.

    Uses the same HTTP discovery helpers as production so the report reflects
    real blockages (anti-bot challenges surface as empty results for that
    engine instead of being bypassed).
    """

    results: list[LinkedInProviderDiagnosticResult] = []

    async with source_session(headers=BROWSER_HEADERS) as session:
        for provider_name in settings.linkedin_post_scraper_search_providers:
            provider_seen_urls: set[str] = set()
            provider_urls: list[str] = []
            family_counts: dict[str, int] = {}
            query_errors = 0
            error_type: str | None = None
            for intent in selected:
                try:
                    search_results = await _fetch_free_search_results(session, provider_name, intent.query)
                except Exception as exc:
                    query_errors += 1
                    error_type = error_type or _sanitized_error_type(exc)
                    continue
                for result in search_results:
                    if len(provider_seen_urls) >= wanted:
                        break
                    url = _canonicalize_linkedin_post_url(_normalize_result_url(result.link))
                    if not url:
                        continue
                    _collect_candidate(
                        LinkedInPostCandidate(
                            url=url,
                            search_title=result.title,
                            snippet=result.snippet,
                            date_text=result.date_text,
                            provider=provider_name,
                            query=intent.query,
                            family=intent.family,
                            language=intent.language,
                        ),
                        intent_family=intent.family,
                        provider_seen_urls=provider_seen_urls,
                        provider_urls=provider_urls,
                        family_counts=family_counts,
                        seen_urls=seen_urls,
                        unique_urls=unique_urls,
                        published_at_hints=published_at_hints,
                    )
            results.append(
                LinkedInProviderDiagnosticResult(
                    provider=provider_name,
                    urls=tuple(provider_urls),
                    error_type=error_type,
                    queries_attempted=len(selected),
                    query_errors=query_errors,
                    family_counts=tuple(family_counts.items()),
                )
            )
    return tuple(results)


async def _fetch_free_search_results(session, provider: str, query: str):
    if provider == "bing_rss":
        return _rss_post_results(await _fetch_bing_rss(session, query))
    html = await _fetch_provider_html(session, provider, query)
    if not html:
        return []
    return _search_html_results(BeautifulSoup(html, "html.parser"))


def _diagnostic_status(
    providers: tuple[LinkedInProviderDiagnosticResult, ...],
    unique_urls: list[str],
) -> DiagnosticStatus:
    error_count = sum(provider.status == "error" for provider in providers)
    if error_count == len(providers):
        return "provider_error"
    if error_count or any(provider.status == "degraded" for provider in providers):
        return "degraded"
    if not unique_urls:
        return "no_results"
    return "ok"


def _sanitized_error_type(exc: Exception) -> str:
    if isinstance(exc, LinkedInSearchProviderError) and exc.status_code is not None:
        return f"Http{exc.status_code}"
    if isinstance(exc, LinkedInSearchProviderError) and exc.failure_type:
        return _SAFE_ERROR_TYPE.sub("_", exc.failure_type)[:80] or "ClientError"
    name = type(exc).__name__ or "Exception"
    sanitized = _SAFE_ERROR_TYPE.sub("_", name)[:80]
    return sanitized or "Exception"


def utcnow() -> datetime:
    return datetime.now(UTC)


def _search_cycle_index(current_time: datetime) -> int:
    return int(current_time.timestamp() // (15 * 60))
