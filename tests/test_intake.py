from tg_vacancy_bot.intake import looks_like_vacancy_message


def test_vacancy_message_with_stack_and_hiring_terms_is_accepted() -> None:
    text = "We are hiring a Senior Backend Engineer. Stack: Python, FastAPI, PostgreSQL. Remote role."

    assert looks_like_vacancy_message(text) is True


def test_linkedin_job_like_message_is_accepted() -> None:
    text = "New developer role: https://www.linkedin.com/posts/example senior react engineer"

    assert looks_like_vacancy_message(text) is True


def test_random_short_message_is_rejected() -> None:
    assert looks_like_vacancy_message("thanks, will check later") is False
