from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

from .arbeitnow_application import build_arbeitnow_application_plan, is_arbeitnow_url
from .models import OperatorProfile


SUBMISSION_SUCCESS_MARKERS = (
    "application submitted",
    "application has been sent",
    "thank you for applying",
    "thank you for your application",
    "vielen dank für deine bewerbung",
    "vielen dank für ihre bewerbung",
)
ARBEITNOW_FORM_SELECTOR = "#form_job_application"
ARBEITNOW_REQUIRED_SELECTORS = (
    "#first_name",
    "#last_name",
    "#email",
    "#cv_or_resume",
    "#terms",
    "#button_send_application",
    "#div_success_message",
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
        """Fill the supported Arbeitnow form and stop before the final submit action."""
        return await self._run_arbeitnow_application(vacancy_url, profile, resume_path, submit=False)

    async def submit_application(
        self,
        vacancy_url: str,
        profile: OperatorProfile | None,
        resume_path: Path | None,
        before_submit: Callable[[], None] | None = None,
    ) -> BrowserInspection:
        """Submit only a verified direct Arbeitnow form and prove the success state."""
        return await self._run_arbeitnow_application(
            vacancy_url,
            profile,
            resume_path,
            submit=True,
            before_submit=before_submit,
        )

    async def _run_arbeitnow_application(
        self,
        vacancy_url: str,
        profile: OperatorProfile | None,
        resume_path: Path | None,
        *,
        submit: bool,
        before_submit: Callable[[], None] | None = None,
    ) -> BrowserInspection:
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
                    if not is_arbeitnow_url(page.url):
                        return BrowserInspection(
                            status="manual_required",
                            error="Arbeitnow redirected the application to an unsupported external site.",
                        )
                    safety_stop = await self._safety_stop(page)
                    if safety_stop:
                        return safety_stop
                    form = page.locator(ARBEITNOW_FORM_SELECTOR)
                    form_changed = await form.count() != 1
                    for selector in ARBEITNOW_REQUIRED_SELECTORS:
                        if await page.locator(selector).count() != 1:
                            form_changed = True
                            break
                    if form_changed:
                        return BrowserInspection(status="manual_required", error="Arbeitnow application form has changed.")
                    await form.locator("#first_name").fill(plan.first_name or "")
                    await form.locator("#last_name").fill(plan.last_name or "")
                    await form.locator("#email").fill(plan.email or "")
                    optional_fields = (
                        ("#phone", plan.phone),
                        ("#personal_url", plan.personal_url),
                        ("#cover_letter", plan.cover_letter),
                    )
                    for selector, value in optional_fields:
                        field = form.locator(selector)
                        field_count = await field.count()
                        if field_count > 1:
                            return BrowserInspection(
                                status="manual_required",
                                error="Arbeitnow application form is ambiguous.",
                            )
                        if value and field_count == 1:
                            await field.fill(value)
                    await form.locator("#cv_or_resume").set_input_files(str(plan.resume_path))
                    await form.locator("#terms").check()
                    if not submit:
                        return BrowserInspection(status="filled", title=await page.title())

                    submit_button = form.locator("#button_send_application")
                    if await submit_button.count() != 1 or not await submit_button.is_enabled():
                        return BrowserInspection(status="manual_required", error="Arbeitnow submit control has changed.")
                    if before_submit:
                        before_submit()
                    await submit_button.click()
                    try:
                        await page.wait_for_function(
                            """
                            () => {
                                const success = document.querySelector('#div_success_message');
                                const visibleSuccess = success && getComputedStyle(success).display !== 'none';
                                const visibleError = Array.from(
                                    document.querySelectorAll('#form_job_application [id^="error-"]')
                                ).some((element) =>
                                    getComputedStyle(element).display !== 'none' &&
                                    (element.textContent || '').trim()
                                );
                                return visibleSuccess || visibleError;
                            }
                            """,
                            timeout=self.timeout_ms,
                        )
                    except PlaywrightTimeoutError:
                        pass
                    success = page.locator("#div_success_message")
                    success_text = await success.inner_text(timeout=self.timeout_ms)
                    form_visible = await form.is_visible()
                    if await success.is_visible() and verified_submission_success(success_text, form_visible):
                        return BrowserInspection(status="submitted", title=await page.title())
                    visible_errors = form.locator('[id^="error-"]:visible')
                    if await visible_errors.count():
                        return BrowserInspection(
                            status="manual_required",
                            error="Arbeitnow rejected one or more application fields.",
                        )
                    return BrowserInspection(
                        status="manual_required",
                        error="The form may have been sent, but the success state could not be verified. Do not retry automatically.",
                    )
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
