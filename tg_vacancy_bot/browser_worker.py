from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright

from .models import OperatorProfile


SUBMISSION_SUCCESS_MARKERS = (
    "application submitted",
    "application has been sent",
    "thank you for applying",
    "thank you for your application",
    "vielen dank für deine bewerbung",
    "vielen dank für ihre bewerbung",
)
def verified_submission_success(body_text: str, form_visible: bool) -> bool:
    body = body_text.lower()
    return not form_visible and any(marker in body for marker in SUBMISSION_SUCCESS_MARKERS)


@dataclass(frozen=True)
class BrowserInspection:
    status: str
    title: str | None = None
    error: str | None = None
    missing_fields: tuple[str, ...] = ()


class BrowserWorker:
    """Safely handles allowlisted forms without login or protection bypasses."""

    def __init__(self, profile_dir: str, allowed_domains: tuple[str, ...], headless: bool, timeout_seconds: int) -> None:
        self.profile_dir = Path(profile_dir)
        self.allowed_domains = allowed_domains
        self.headless = headless
        self.timeout_ms = timeout_seconds * 1000

    async def inspect(self, url: str) -> BrowserInspection:
        hostname = (urlparse(url).hostname or "").lower()
        if not self._allowed(hostname):
            return BrowserInspection(status="unsupported_site", error="Domain is not in APPLICATION_ALLOWED_DOMAINS.")
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        try:
            async with async_playwright() as playwright:
                context = await playwright.chromium.launch_persistent_context(
                    str(self.profile_dir), headless=self.headless, viewport={"width": 1280, "height": 900}
                )
                try:
                    page = await context.new_page()
                    page.set_default_timeout(self.timeout_ms)
                    await page.goto(url, wait_until="domcontentloaded", timeout=self.timeout_ms)
                    safety_stop = await self._safety_stop(page)
                    if safety_stop:
                        return safety_stop
                    return BrowserInspection(status="parsed", title=await page.title())
                finally:
                    await context.close()
        except Exception as exc:
            return BrowserInspection(status="failed", error=f"Browser inspection failed: {type(exc).__name__}")

    async def prepare_application(
        self, vacancy_url: str, profile: OperatorProfile | None, resume_path: Path | None,
    ) -> BrowserInspection:
        return BrowserInspection(status="unsupported_site", error="No application adapter is registered for this site.")

    async def submit_application(
        self,
        vacancy_url: str,
        profile: OperatorProfile | None,
        resume_path: Path | None,
        before_submit: Callable[[], None] | None = None,
    ) -> BrowserInspection:
        return BrowserInspection(status="unsupported_site", error="No application adapter is registered for this site.")

    async def _safety_stop(self, page) -> BrowserInspection | None:
        body = (await page.locator("body").inner_text(timeout=self.timeout_ms)).lower()
        if any(marker in body for marker in ("captcha", "recaptcha", "hcaptcha", "two-factor", "2fa")):
            return BrowserInspection(status="manual_required", error="Site protection detected.")
        if await page.locator('input[type="password"]').count():
            return BrowserInspection(status="manual_required", error="Login is required.")
        return None

    def _allowed(self, hostname: str) -> bool:
        return any(hostname == domain or hostname.endswith(f".{domain}") for domain in self.allowed_domains)
