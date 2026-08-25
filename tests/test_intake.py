import pytest

from tg_vacancy_bot.intake import looks_like_vacancy_message


def test_junior_frontend_message_is_accepted() -> None:
    text = "We are hiring a Junior Frontend Developer. Stack: React, TypeScript, Next.js. Remote role."

    assert looks_like_vacancy_message(text) is True


def test_russian_junior_fullstack_message_is_accepted() -> None:
    text = "Ищем джуниор фулстек-разработчика в команду. Стек: Python, Django, React. Удаленно."

    assert looks_like_vacancy_message(text) is True


def test_trainee_frontend_internship_message_is_accepted() -> None:
    text = "Internship open role: Trainee Front-End Developer. HTML, CSS, JavaScript. We welcome beginners."

    assert looks_like_vacancy_message(text) is True


def test_senior_frontend_message_is_rejected() -> None:
    text = "We are hiring a Senior Frontend Engineer. Stack: React, GraphQL. Remote role."

    assert looks_like_vacancy_message(text) is False


def test_middle_fullstack_with_junior_wording_is_rejected() -> None:
    text = "Junior-friendly product team is hiring a Middle Fullstack Developer. React and Node.js."

    assert looks_like_vacancy_message(text) is False


def test_junior_backend_message_is_rejected() -> None:
    text = "We are hiring a Junior Backend Developer. Stack: Python, FastAPI, PostgreSQL. Remote role."

    assert looks_like_vacancy_message(text) is False


def test_non_development_it_role_is_rejected() -> None:
    text = "We are hiring a Product Manager for a software platform. Remote role."

    assert looks_like_vacancy_message(text) is False


@pytest.mark.parametrize(
    "text",
    [
        "We are hiring an Engineering Manager to lead backend developers.",
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
