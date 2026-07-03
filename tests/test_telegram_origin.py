from types import SimpleNamespace

from tg_vacancy_bot.telegram_origin import forwarded_public_post_url


def test_forwarded_public_post_url_from_channel_origin() -> None:
    message = SimpleNamespace(
        forward_origin=SimpleNamespace(
            chat=SimpleNamespace(username="it_jobs_board"),
            message_id=123,
        )
    )

    assert forwarded_public_post_url(message) == "https://t.me/it_jobs_board/123"


def test_forwarded_public_post_url_returns_none_for_private_origin() -> None:
    message = SimpleNamespace(
        forward_origin=SimpleNamespace(
            chat=SimpleNamespace(username=None),
            message_id=123,
        )
    )

    assert forwarded_public_post_url(message) is None
