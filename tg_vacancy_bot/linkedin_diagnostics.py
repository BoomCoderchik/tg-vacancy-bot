from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal, Protocol

from tg_vacancy_bot.config import Settings
from tg_vacancy_bot.sources.adapters.linkedin_post_search import (
    LinkedInPostCandidate,
    LinkedInPostSearchAdapter,
    LinkedInPostSerperAdapter,
    LinkedInSearchProviderError,
    _published_at_for_result,
)
from tg_vacancy_bot.sources.linkedin_search_profile import (
    fair_query_limits,
    select_cycle_intents,
    select_search_intents,
)


DiagnosticStatus = Literal[
    "misconfigured",
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
    """Run configured keyed discovery providers without browser or publishing side effects."""

    current_time = utcnow()
    wanted = min(max(limit, 0), MAX_DIAGNOSTIC_RESULTS_PER_PROVIDER)
    provider_types: list[tuple[str, type[_DiscoveryProvider]]] = []
    if settings.serpapi_api_key.strip():
        provider_types.append(("serpapi", LinkedInPostSearchAdapter))
    if settings.serper_api_key.strip():
        provider_types.append(("serper", LinkedInPostSerperAdapter))

    all_intents = select_search_intents(settings.linkedin_post_headless_query)
    selected = select_cycle_intents(
        all_intents,
        max_intents=settings.linkedin_post_search_intents_per_cycle,
        cycle_index=_search_cycle_index(current_time),
    )
    query_limits = fair_query_limits(max(wanted, len(selected)), selected)
    intent_labels = tuple(f"{intent.family}:{intent.language}" for intent in selected)

    permission_gate = _permission_gate(settings)
    if not provider_types:
        return LinkedInDiagnosticReport(
            status="misconfigured",
            permission_gate=permission_gate,
            providers=(),
            urls=(),
            selected_intents=intent_labels,
            total_profile_intents=len(all_intents),
        )

    provider_results: list[LinkedInProviderDiagnosticResult] = []
    unique_urls: list[str] = []
    seen_urls: set[str] = set()
    published_at_hints: dict[str, datetime | None] = {}

    for provider_name, provider_type in provider_types:
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
                url = str(candidate.url).strip()
                if not url or url in provider_seen_urls:
                    continue
                provider_seen_urls.add(url)
                provider_urls.append(url)
                family_counts[intent.family] = family_counts.get(intent.family, 0) + 1
                published_at = _published_at_for_result(candidate.date_text, url)
                if url not in seen_urls:
                    seen_urls.add(url)
                    unique_urls.append(url)
                    published_at_hints[url] = published_at
                elif published_at_hints[url] is None and published_at is not None:
                    published_at_hints[url] = published_at

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
