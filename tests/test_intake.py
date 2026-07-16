import pytest

from tg_vacancy_bot.intake import looks_like_vacancy_message


def test_vacancy_message_with_stack_and_hiring_terms_is_accepted() -> None:
    text = "We are hiring a Senior Backend Engineer. Stack: Python, FastAPI, PostgreSQL. Remote role."

    assert looks_like_vacancy_message(text) is True


def test_linkedin_job_like_message_is_accepted() -> None:
    text = "New developer role: https://www.linkedin.com/posts/example senior react engineer"

    assert looks_like_vacancy_message(text) is True


def test_non_development_it_role_is_rejected() -> None:
    text = "We are hiring a Product Manager for a software platform. Remote role."

    assert looks_like_vacancy_message(text) is False


@pytest.mark.parametrize(
    "text",
    [
        "We are hiring an Engineering Manager to lead backend developers.",
        "Open role: Technical PM for a Python developer platform.",
        "Vacancy: SDET for automated browser testing.",
        "Looking for an Implementation Engineer to write scripts and integrations.",
    ],
)
def test_policy_excluded_roles_are_rejected_from_manual_intake(text: str) -> None:
    assert looks_like_vacancy_message(text) is False


def test_cleaner_at_it_company_is_rejected() -> None:
    text = "We are hiring a Cleaner at an IT software company. Office work for a platform team."

    assert looks_like_vacancy_message(text) is False


def test_uborschik_at_it_company_is_rejected() -> None:
    text = "Вакансия: уборщик в IT компанию. Работа в офисе software platform."

    assert looks_like_vacancy_message(text) is False


def test_random_short_message_is_rejected() -> None:
    assert looks_like_vacancy_message("thanks, will check later") is False
