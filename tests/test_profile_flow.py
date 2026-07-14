import pytest

from tg_vacancy_bot.models import OperatorProfile
from tg_vacancy_bot.profile_flow import (
    MAX_EXTRA_FIELDS,
    clean_profile_value,
    format_profile_summary,
    is_profile_operator,
    parse_extra_field,
    profile_with_extra_field,
    profile_with_field,
)


def test_profile_operator_requires_configured_allowlist() -> None:
    assert is_profile_operator(123, ()) is False
    assert is_profile_operator(None, (123,)) is False
    assert is_profile_operator(456, (123,)) is False
    assert is_profile_operator(123, (123,)) is True


def test_profile_fields_and_summary_escape_private_values() -> None:
    profile = profile_with_field(OperatorProfile(operator_user_id=123), "full_name", "Ada <Lovelace>")
    profile = profile_with_extra_field(profile, "portfolio", "https://example.test/?a=<b>")

    summary = format_profile_summary(profile)

    assert "Ada &lt;Lovelace&gt;" in summary
    assert "https://example.test/?a=&lt;b&gt;" in summary
    assert "Резюме:</b> не указано" in summary


def test_profile_value_normalization_and_extra_field_validation() -> None:
    assert clean_profile_value("  value  ") == "value"
    assert clean_profile_value("Пропустить") is None
    assert parse_extra_field("notice period: 2 weeks") == ("notice period", "2 weeks")

    with pytest.raises(ValueError, match="формате"):
        parse_extra_field("not valid")


def test_profile_limits_extra_fields() -> None:
    profile = OperatorProfile(operator_user_id=123)
    for index in range(MAX_EXTRA_FIELDS):
        profile = profile_with_extra_field(profile, f"field-{index}", "value")

    with pytest.raises(ValueError, match="не больше"):
        profile_with_extra_field(profile, "one-more", "value")
