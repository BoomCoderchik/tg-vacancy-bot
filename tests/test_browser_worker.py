import asyncio

from tg_vacancy_bot.browser_worker import (
    ARBEITNOW_FORM_SELECTOR,
    ARBEITNOW_REQUIRED_SELECTORS,
    BrowserWorker,
    verified_submission_success,
)
from tg_vacancy_bot.models import OperatorProfile


def test_browser_worker_rejects_unapproved_domain_without_browser(tmp_path) -> None:
    worker = BrowserWorker(str(tmp_path / "profile"), ("example.com",), True, 1)

    result = asyncio.run(worker.inspect("https://not-allowed.example.org/job"))

    assert result.status == "unsupported_site"
    assert "APPLICATION_ALLOWED_DOMAINS" in result.error


def test_browser_worker_accepts_subdomains_in_allowlist(tmp_path) -> None:
    worker = BrowserWorker(str(tmp_path / "profile"), ("example.com",), True, 1)

    assert worker._allowed("jobs.example.com") is True
    assert worker._allowed("example.org") is False


def test_browser_worker_requires_profile_data_before_opening_arbeitnow(tmp_path) -> None:
    worker = BrowserWorker(str(tmp_path / "profile"), ("arbeitnow.com",), True, 1)

    result = asyncio.run(
        worker.prepare_application("https://www.arbeitnow.com/jobs/example", OperatorProfile(operator_user_id=1), None)
    )

    assert result.status == "profile_missing"
    assert result.missing_fields == ("full_name", "email", "resume")


def test_browser_worker_uses_current_arbeitnow_inline_form_contract() -> None:
    assert ARBEITNOW_FORM_SELECTOR == "#form_job_application"
    assert ARBEITNOW_REQUIRED_SELECTORS == (
        "#first_name",
        "#last_name",
        "#email",
        "#cv_or_resume",
        "#terms",
        "#button_send_application",
        "#div_success_message",
    )


def test_browser_worker_requires_proof_before_reporting_submission() -> None:
    assert verified_submission_success(
        "Your job application has been sent successfully. Good luck!",
        form_visible=False,
    ) is True
    assert verified_submission_success("Thank you for your application", form_visible=False) is True
    assert verified_submission_success("Thank you for your application", form_visible=True) is False
    assert verified_submission_success("The form was accepted", form_visible=False) is False
