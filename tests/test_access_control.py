import pytest

from tg_vacancy_bot.access_control import (
    is_authorized_user,
    parse_operator_user_ids,
    unauthorized_reply_text,
)


def test_parse_operator_user_ids_accepts_commas_and_semicolons() -> None:
    assert parse_operator_user_ids("123, 456;123") == (123, 456)


def test_parse_operator_user_ids_rejects_invalid_values() -> None:
    with pytest.raises(RuntimeError, match="Invalid OPERATOR_USER_IDS"):
        parse_operator_user_ids("123, nope")


def test_is_authorized_user_denies_everyone_when_allowlist_empty() -> None:
    # Closed by default: an empty OPERATOR_USER_IDS must never mean "allow all",
    # otherwise any Telegram user could publish into the target channel.
    assert is_authorized_user(None, ()) is False
    assert is_authorized_user(123, ()) is False


def test_unauthorized_reply_explains_onboarding_when_allowlist_empty() -> None:
    text = unauthorized_reply_text(())
    assert "OPERATOR_USER_IDS" in text
    assert "/whoami" in text


def test_unauthorized_reply_does_not_leak_allowlist() -> None:
    text = unauthorized_reply_text((123456789, 987654321))
    assert text == "Not authorized."
    assert "123456789" not in text


def test_is_authorized_user_checks_allowlist() -> None:
    assert is_authorized_user(123, (123, 456)) is True
    assert is_authorized_user(789, (123, 456)) is False
    assert is_authorized_user(None, (123, 456)) is False
