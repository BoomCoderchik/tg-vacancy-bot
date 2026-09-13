import asyncio
from datetime import UTC, datetime

import pytest
from bs4 import BeautifulSoup

from tg_vacancy_bot.config import Settings
from tg_vacancy_bot.sources.adapters import telegram_vacancy_channel
from tg_vacancy_bot.sources.adapters.telegram_vacancy_channel import (
    TelegramVacancyChannelAdapter,
    _post_to_vacancy,
    _published_at_for_post,
)


_DEFAULT_DATE_HTML = '<time datetime="2026-09-12T10:30:00+00:00">10:30</time>'


def _post_block(
    post_id,
    *,
    username="jobs_chan",
    text="Junior Frontend Developer.\nWe are hiring a junior frontend developer.",
    date_html=None,
    include_link=True,
) -> str:
    date = _DEFAULT_DATE_HTML if date_html is None else date_html
    link = (
        f'<a class="tgme_widget_message_date" href="https://t.me/{username}/{post_id}">{date}</a>'
        if include_link
        else ""
    )
    return (
        f'<div class="tgme_widget_message" data-post="{username}/{post_id}">'
        f'<div class="tgme_widget_message_text" dir="auto">{text}</div>'
        f"{link}</div>"
    )


def _channel_page(blocks) -> str:
    return f"<html><body>{''.join(blocks)}</body></html>"


def _make_session(pages, statuses=None):
    pages = dict(pages)
    statuses = statuses or {}

    class FakeResponse:
        def __init__(self, url, status, text):
            self.url = url
            self.status = status
            self._text = text

        def raise_for_status(self):
            if self.status >= 400:
                raise RuntimeError(f"HTTP {self.status}")

        async def text(self):
            return self._text

    class FakeGet:
        def __init__(self, response):
            self._response = response

        async def __aenter__(self):
            return self._response

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            return False

    class FakeSession:
        def __init__(self):
            self.requested = []

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            return False

        def get(self, url):
            self.requested.append(url)
            return FakeGet(FakeResponse(url, statuses.get(url, 200), pages.get(url, "")))

    return FakeSession()


def _install_session(monkeypatch, pages, statuses=None):
    session = _make_session(pages, statuses)
    monkeypatch.setattr(telegram_vacancy_channel, "source_session", lambda **kwargs: session)
    return session


def _run_fetch(settings):
    return asyncio.run(TelegramVacancyChannelAdapter(settings).fetch())


def test_post_with_iso_datetime_passes_freshness(monkeypatch) -> None:
    current = datetime(2026, 9, 13, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(telegram_vacancy_channel, "utcnow", lambda: current)
    html = _channel_page([_post_block(post_id=101)])
    _install_session(monkeypatch, {"https://t.me/s/jobs_chan": html})

    settings = Settings(
        RUSSIA_TELEGRAM_CHANNELS="jobs_chan",
        RUSSIA_TELEGRAM_MAX_POSTS_PER_CHANNEL=5,
        SOURCE_MAX_AGE_HOURS=48,
    )
    vacancies = _run_fetch(settings)

    assert len(vacancies) == 1
    vacancy = vacancies[0]
    assert vacancy.published_at == datetime(2026, 9, 12, 10, 30, tzinfo=UTC)
    assert vacancy.url == "https://t.me/jobs_chan/101"
    assert vacancy.source == "Telegram (jobs_chan)"
    assert "Junior Frontend Developer" in vacancy.title
    assert "junior frontend developer" in vacancy.description.lower()
    assert vacancy.location is None
    assert vacancy.stack == ()
    assert vacancy.salary is None


def test_time_only_text_date_resolves_to_today(monkeypatch) -> None:
    current = datetime(2026, 9, 13, 8, 0, tzinfo=UTC)
    monkeypatch.setattr(telegram_vacancy_channel, "utcnow", lambda: current)
    html = _channel_page(
        [_post_block(post_id=1, text="Вакансия джуниор фронтенд", date_html="<time>14:32</time>")]
    )
    _install_session(monkeypatch, {"https://t.me/s/jobs_chan": html})

    settings = Settings(RUSSIA_TELEGRAM_CHANNELS="jobs_chan", RUSSIA_TELEGRAM_MAX_POSTS_PER_CHANNEL=5)
    vacancies = _run_fetch(settings)

    assert vacancies[0].published_at == datetime(2026, 9, 13, 14, 32, tzinfo=UTC)


def test_relative_text_date_yesterday(monkeypatch) -> None:
    current = datetime(2026, 9, 13, 8, 0, tzinfo=UTC)
    monkeypatch.setattr(telegram_vacancy_channel, "utcnow", lambda: current)
    html = _channel_page(
        [_post_block(post_id=2, text="Вакансия джуниор фронтенд", date_html="<time>вчера</time>")]
    )
    _install_session(monkeypatch, {"https://t.me/s/jobs_chan": html})

    settings = Settings(RUSSIA_TELEGRAM_CHANNELS="jobs_chan", RUSSIA_TELEGRAM_MAX_POSTS_PER_CHANNEL=5)
    vacancies = _run_fetch(settings)

    assert vacancies[0].published_at == datetime(2026, 9, 12, 8, 0, tzinfo=UTC)


def test_undated_post_kept_by_freshness_filter(monkeypatch) -> None:
    current = datetime(2026, 9, 13, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(telegram_vacancy_channel, "utcnow", lambda: current)
    html = _channel_page([_post_block(post_id=3, date_html="")])
    _install_session(monkeypatch, {"https://t.me/s/jobs_chan": html})

    settings = Settings(
        RUSSIA_TELEGRAM_CHANNELS="jobs_chan",
        RUSSIA_TELEGRAM_MAX_POSTS_PER_CHANNEL=5,
        SOURCE_MAX_AGE_HOURS=48,
    )
    vacancies = _run_fetch(settings)

    assert len(vacancies) == 1
    assert vacancies[0].published_at is None


def test_empty_text_post_is_skipped(monkeypatch) -> None:
    empty_text_blocks = _post_block(post_id=4, text="   ")
    no_text_block = (
        '<div class="tgme_widget_message" data-post="jobs_chan/5">'
        '<a class="tgme_widget_message_date" href="https://t.me/jobs_chan/5">'
        '<time datetime="2026-09-12T10:30:00+00:00">10:30</time></a></div>'
    )
    html = _channel_page([empty_text_blocks, no_text_block])
    _install_session(monkeypatch, {"https://t.me/s/jobs_chan": html})

    settings = Settings(RUSSIA_TELEGRAM_CHANNELS="jobs_chan", RUSSIA_TELEGRAM_MAX_POSTS_PER_CHANNEL=5)
    vacancies = _run_fetch(settings)

    assert vacancies == []


def test_failing_channel_skipped_while_others_are_processed(monkeypatch) -> None:
    current = datetime(2026, 9, 13, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(telegram_vacancy_channel, "utcnow", lambda: current)
    good_html = _channel_page([_post_block(post_id=1, username="good_chan")])
    _install_session(monkeypatch, {"https://t.me/s/good_chan": good_html})

    real_fetch_channel = telegram_vacancy_channel._fetch_channel

    async def flaky_fetch_channel(session, username, limit, seen_urls):
        if username == "broken_chan":
            raise RuntimeError("channel unavailable")
        return await real_fetch_channel(session, username, limit, seen_urls)

    monkeypatch.setattr(telegram_vacancy_channel, "_fetch_channel", flaky_fetch_channel)
    settings = Settings(
        RUSSIA_TELEGRAM_CHANNELS="broken_chan,good_chan",
        RUSSIA_TELEGRAM_MAX_POSTS_PER_CHANNEL=5,
    )
    vacancies = _run_fetch(settings)

    assert [vacancy.source for vacancy in vacancies] == ["Telegram (good_chan)"]


def test_http_error_channel_skipped_without_breaking_others(monkeypatch) -> None:
    current = datetime(2026, 9, 13, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(telegram_vacancy_channel, "utcnow", lambda: current)
    good_html = _channel_page([_post_block(post_id=1, username="good_chan")])
    _install_session(
        monkeypatch,
        {"https://t.me/s/good_chan": good_html},
        statuses={"https://t.me/s/broken_chan": 500},
    )
    settings = Settings(
        RUSSIA_TELEGRAM_CHANNELS="broken_chan,good_chan",
        RUSSIA_TELEGRAM_MAX_POSTS_PER_CHANNEL=5,
    )
    vacancies = _run_fetch(settings)

    assert [vacancy.source for vacancy in vacancies] == ["Telegram (good_chan)"]


def test_not_found_channel_skipped(monkeypatch) -> None:
    _install_session(monkeypatch, {}, statuses={"https://t.me/s/missing_chan": 404})
    settings = Settings(RUSSIA_TELEGRAM_CHANNELS="missing_chan", RUSSIA_TELEGRAM_MAX_POSTS_PER_CHANNEL=5)
    vacancies = _run_fetch(settings)

    assert vacancies == []


def test_channels_are_normalized_without_at_sign(monkeypatch) -> None:
    settings = Settings(
        RUSSIA_TELEGRAM_CHANNELS="@vacancies_ru, jobs_chan ",
        RUSSIA_TELEGRAM_MAX_POSTS_PER_CHANNEL=5,
    )
    assert settings.russia_telegram_channels == ("vacancies_ru", "jobs_chan")

    session = _install_session(monkeypatch, {})
    vacancies = _run_fetch(settings)

    assert vacancies == []
    assert session.requested == ["https://t.me/s/vacancies_ru", "https://t.me/s/jobs_chan"]


def test_empty_channels_return_no_vacancies(monkeypatch) -> None:
    _install_session(monkeypatch, {})
    settings = Settings(RUSSIA_TELEGRAM_CHANNELS="", RUSSIA_TELEGRAM_MAX_POSTS_PER_CHANNEL=5)
    vacancies = _run_fetch(settings)

    assert vacancies == []


def test_max_posts_per_channel_limit_is_enforced(monkeypatch) -> None:
    current = datetime(2026, 9, 13, 12, 0, tzinfo=UTC)
    monkeypatch.setattr(telegram_vacancy_channel, "utcnow", lambda: current)
    blocks = [
        _post_block(post_id=post_id, date_html=f'<time datetime="2026-09-13T0{post_id}:00:00+00:00">0{post_id}:00</time>')
        for post_id in range(1, 6)
    ]
    html = _channel_page(blocks)
    _install_session(monkeypatch, {"https://t.me/s/jobs_chan": html})

    settings = Settings(
        RUSSIA_TELEGRAM_CHANNELS="jobs_chan",
        RUSSIA_TELEGRAM_MAX_POSTS_PER_CHANNEL=2,
        SOURCE_MAX_AGE_HOURS=48,
    )
    vacancies = _run_fetch(settings)

    assert [vacancy.url for vacancy in vacancies] == [
        "https://t.me/jobs_chan/1",
        "https://t.me/jobs_chan/2",
    ]


def test_post_without_link_or_data_post_is_skipped(monkeypatch) -> None:
    broken_blocks = [
        '<div class="tgme_widget_message" data-post="">'
        '<div class="tgme_widget_message_text">No post id</div></div>',
        '<div class="tgme_widget_message">'
        '<div class="tgme_widget_message_text">No data at all</div></div>',
    ]
    html = _channel_page(broken_blocks)
    _install_session(monkeypatch, {"https://t.me/s/jobs_chan": html})

    settings = Settings(RUSSIA_TELEGRAM_CHANNELS="jobs_chan", RUSSIA_TELEGRAM_MAX_POSTS_PER_CHANNEL=5)
    vacancies = _run_fetch(settings)

    assert vacancies == []


def test_month_day_text_date_uses_current_year() -> None:
    current = datetime(2026, 9, 13, 8, 0, tzinfo=UTC)
    soup = BeautifulSoup('<a class="tgme_widget_message_date"><time>Sep 12</time></a>', "html.parser")
    parsed = _published_at_for_post(soup.find("a"), current)
    assert parsed == datetime(2026, 9, 12, 0, 0, tzinfo=UTC)

    reversed_soup = BeautifulSoup('<a class="tgme_widget_message_date"><time>12 Sep</time></a>', "html.parser")
    parsed_reversed = _published_at_for_post(reversed_soup.find("a"), current)
    assert parsed_reversed == datetime(2026, 9, 12, 0, 0, tzinfo=UTC)


def test_month_day_future_dates_roll_back_a_year() -> None:
    current = datetime(2026, 9, 13, 8, 0, tzinfo=UTC)
    soup = BeautifulSoup('<a class="tgme_widget_message_date"><time>Sep 30</time></a>', "html.parser")
    parsed = _published_at_for_post(soup.find("a"), current)
    assert parsed == datetime(2025, 9, 30, 0, 0, tzinfo=UTC)


def test_post_to_vacancy_deduplicates_by_url() -> None:
    block_html = '<div class="tgme_widget_message" data-post="jobs_chan/7">' \
        '<div class="tgme_widget_message_text">Same URL</div>' \
        '<a class="tgme_widget_message_date" href="https://t.me/jobs_chan/7">' \
        '<time datetime="2026-09-12T10:30:00+00:00">10:30</time></a></div>'
    seen = set()
    soup = BeautifulSoup(block_html, "html.parser")
    block = soup.select_one("div.tgme_widget_message")

    first = _post_to_vacancy(block, "jobs_chan", seen)
    second = _post_to_vacancy(block, "jobs_chan", seen)

    assert first is not None
    assert second is None