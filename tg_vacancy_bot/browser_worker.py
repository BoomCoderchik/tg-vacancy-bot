from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import async_playwright

from .arbeitnow_application import build_arbeitnow_application_plan, is_arbeitnow_url
from .models import OperatorProfile


@dataclass(frozen=True)
class BrowserInspection:
    status: str
    title: str | None = None
    error: str | None = None
    missing_fields: tuple[str, ...] = ()


class BrowserWorker:
    """Safely inspects and prepares allowlisted forms; it never logs in or submits them."""

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
        """Fill the supported Arbeitnow form and stop before the final submit action."""
        if not is_arbeitnow_url(vacancy_url):
            return BrowserInspection(status="unsupported_site", error="No application adapter is registered for this site.")
        plan = build_arbeitnow_application_plan(vacancy_url, profile, resume_path)
        if plan.missing_fields:
            return BrowserInspection(
                status="profile_missing",
                error="Required application data is missing.",
                missing_fields=plan.missing_fields,
            )
        hostname = (urlparse(plan.application_url).hostname or "").lower()
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
                    await page.goto(plan.application_url, wait_until="domcontentloaded", timeout=self.timeout_ms)
                    safety_stop = await self._safety_stop(page)
                    if safety_stop:
                        return safety_stop
                    required_selectors = ("#first_name", "#last_name", "#email", "#cv", "#terms_of_service")
                    if any(await page.locator(selector).count() != 1 for selector in required_selectors):
                        return BrowserInspection(status="manual_required", error="Arbeitnow application form has changed.")
                    await page.locator("#first_name").fill(plan.first_name or "")
                    await page.locator("#last_name").fill(plan.last_name or "")
                    await page.locator("#email").fill(plan.email or "")
                    if plan.phone:
                        await page.locator("#phone").fill(plan.phone)
                    if plan.personal_url:
                        await page.locator("#personal_url").fill(plan.personal_url)
                    if plan.cover_letter:
                        await page.locator("#cover_letter").fill(plan.cover_letter)
                    await page.locator("#cv").set_input_files(str(plan.resume_path))
                    await page.locator("#terms_of_service").check()
                    return BrowserInspection(status="filled", title=await page.title())
                finally:
                    await context.close()
        except Exception as exc:
            return BrowserInspection(status="failed", error=f"Browser preparation failed: {type(exc).__name__}")

    async def _safety_stop(self, page) -> BrowserInspection | None:
        body = (await page.locator("body").inner_text(timeout=self.timeout_ms)).lower()
        if any(marker in body for marker in ("captcha", "recaptcha", "hcaptcha", "two-factor", "2fa")):
            return BrowserInspection(status="manual_required", error="Site protection detected.")
        if await page.locator('input[type="password"]').count():
            return BrowserInspection(status="manual_required", error="Login is required.")
        return None

    def _allowed(self, hostname: str) -> bool:
        return any(hostname == domain or hostname.endswith(f".{domain}") for domain in self.allowed_domains)
