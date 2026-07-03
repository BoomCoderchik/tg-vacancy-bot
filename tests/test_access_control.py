import pytest

from tg_vacancy_bot.access_control import is_authorized_user, parse_operator_user_ids


def test_parse_operator_user_ids_accepts_commas_and_semicolons() -> None:
    assert parse_operator_user_ids("123, 456;123") == (123, 456)


def test_parse_operator_user_ids_rejects_invalid_values() -> None:
    with pytest.raises(RuntimeError, match="Invalid OPERATOR_USER_IDS"):
        parse_operator_user_ids("123, nope")


def test_is_authorized_user_allows_all_when_allowlist_empty() -> None:
    assert is_authorized_user(None, ()) is True
    assert is_authorized_user(123, ()) is True


def test_is_authorized_user_checks_allowlist() -> None:
    assert is_authorized_user(123, (123, 456)) is True
    assert is_authorized_user(789, (123, 456)) is False
    assert is_authorized_user(None, (123, 456)) is False
