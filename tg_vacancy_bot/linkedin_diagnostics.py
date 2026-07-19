from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal, Protocol

from tg_vacancy_bot.config import Settings
from tg_vacancy_bot.sources.adapters.linkedin_post_search import (
    LinkedInPostCandidate,
    LinkedInPostSearchAdapter,
    LinkedInPostSerperAdapter,
)


DiagnosticStatus = Literal[
    "misconfigured",
    "no_results",
    "ok",
    "degraded",
    "provider_error",
]
PermissionGateState = Literal["authorized", "not_authorized", "incomplete"]
ProviderStatus = Literal["ok", "error"]

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

    @property
    def status(self) -> ProviderStatus:
        return "error" if self.error_type else "ok"

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

    wanted = min(max(limit, 0), MAX_DIAGNOSTIC_RESULTS_PER_PROVIDER)
    configured_providers: list[tuple[str, _DiscoveryProvider]] = []
    if settings.serpapi_api_key.strip():
        configured_providers.append(("serpapi", LinkedInPostSearchAdapter(settings)))
    if settings.serper_api_key.strip():
        configured_providers.append(("serper", LinkedInPostSerperAdapter(settings)))

    permission_gate = _permission_gate(settings)
    if not configured_providers:
        return LinkedInDiagnosticReport(
            status="misconfigured",
            permission_gate=permission_gate,
            providers=(),
            urls=(),
        )

    provider_results: list[LinkedInProviderDiagnosticResult] = []
    unique_urls: list[str] = []
    seen_urls: set[str] = set()

    for provider_name, adapter in configured_providers:
        try:
            candidates = await adapter.discover(limit=wanted)
        except Exception as exc:
            provider_results.append(
                LinkedInProviderDiagnosticResult(
                    provider=provider_name,
                    error_type=_sanitized_error_type(exc),
                )
            )
            continue

        provider_urls: list[str] = []
        provider_seen_urls: set[str] = set()
        for candidate in candidates:
            url = str(candidate.url).strip()
            if not url or url in provider_seen_urls:
                continue
            provider_seen_urls.add(url)
            provider_urls.append(url)
            if url not in seen_urls:
                seen_urls.add(url)
                unique_urls.append(url)

        provider_results.append(
            LinkedInProviderDiagnosticResult(
                provider=provider_name,
                urls=tuple(provider_urls),
            )
        )

    results = tuple(provider_results)
    return LinkedInDiagnosticReport(
        status=_diagnostic_status(results, unique_urls),
        permission_gate=permission_gate,
        providers=results,
        urls=tuple(unique_urls),
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
            f"candidates={report.candidate_count} unique={report.unique_count}"
        ),
    ]
    for provider in report.providers:
        line = (
            f"provider={provider.provider} status={provider.status} "
            f"candidates={provider.candidate_count}"
        )
        if provider.error_type:
            line += f" error_type={provider.error_type}"
        lines.append(line)

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
    if error_count:
        return "degraded"
    if not unique_urls:
        return "no_results"
    return "ok"


def _sanitized_error_type(exc: Exception) -> str:
    name = type(exc).__name__ or "Exception"
    sanitized = _SAFE_ERROR_TYPE.sub("_", name)[:80]
    return sanitized or "Exception"
