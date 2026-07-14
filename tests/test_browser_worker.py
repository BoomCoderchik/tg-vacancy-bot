import asyncio

from tg_vacancy_bot.browser_worker import BrowserWorker


def test_browser_worker_rejects_unapproved_domain_without_browser(tmp_path) -> None:
    worker = BrowserWorker(str(tmp_path / "profile"), ("example.com",), True, 1)

    result = asyncio.run(worker.inspect("https://not-allowed.example.org/job"))

    assert result.status == "unsupported_site"
    assert "APPLICATION_ALLOWED_DOMAINS" in result.error


def test_browser_worker_accepts_subdomains_in_allowlist(tmp_path) -> None:
    worker = BrowserWorker(str(tmp_path / "profile"), ("example.com",), True, 1)

    assert worker._allowed("jobs.example.com") is True
    assert worker._allowed("example.org") is False
