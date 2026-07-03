from tg_vacancy_bot.telegram_check import TelegramCheckResult, format_check_result


def test_format_check_result_does_not_include_token() -> None:
    result = TelegramCheckResult(
        bot_username="vacancy_bot",
        target_title="IT Jobs",
        target_type="channel",
        membership_status="administrator",
        can_post_messages=True,
    )

    text = format_check_result(result)

    assert "Telegram check OK" in text
    assert "@vacancy_bot" in text
    assert "IT Jobs" in text
    assert "Can post messages: yes" in text
    assert "TOKEN" not in text
