import pytest

from tg_vacancy_bot.sources.filters import evaluate_vacancy_policy


@pytest.mark.parametrize(
    "text",
    [
        "We are hiring a Junior Frontend Developer to build React UI components.",
        "Looking for a Frontend Intern. TypeScript, Next.js. DM me your CV!",
        "Open role for an entry-level front-end developer. HTML, CSS, JS.",
        "Ищем джуниор фронтенд-разработчика в команду. Стек: Vue, TypeScript.",
        "Открыта вакансия стажера-фронтенд разработчика в команду разработки.",
        "We are hiring a Junior Fullstack Developer (React + Node.js) for our product team.",
        "Ищем стажера fullstack-разработчика без опыта. Python, Django, React.",
        "Join our team as a trainee full-stack engineer and start your IT career!",
    ],
)
def test_junior_frontend_fullstack_posts_are_accepted(text: str) -> None:
    decision = evaluate_vacancy_policy(text)

    assert decision.allowed is True


@pytest.mark.parametrize(
    ("text", "expected_reason"),
    [
        ("We are hiring a Junior Backend Developer. FastAPI.", "no_frontend_fullstack_role"),
        ("Ищем джуна-разработчика в дружную команду.", "no_frontend_fullstack_role"),
        ("We are hiring a Frontend Developer. React, TypeScript.", "no_junior_level_evidence"),
        ("Ищем опытного фронтенд-разработчика в команду.", "no_junior_level_evidence"),
        (
            "Junior-friendly team! We are hiring a Middle Frontend Developer for our product.",
            "non_junior_seniority_for_role",
        ),
        (
            "Our product startup seeks a Senior Fullstack Developer; juniors can learn from the team.",
            "non_junior_seniority_for_role",
        ),
        ("Junior Frontend Developer. React, TypeScript, remote.", "no_hiring_intent"),
        ("Джун-фронтендер, React, портфолио.", "no_hiring_intent"),
        ("Frontend bootcamp for juniors — enroll now!", "excluded_context"),
        ("Курс по frontend-разработке для джунов.", "excluded_context"),
        ("Looking for a mentor to guide junior frontend developers.", "excluded_context"),
        ("Ищем ментора для джуниора-фронтендера.", "excluded_context"),
    ],
)
def test_rejected_posts_report_diagnostic_reason(text: str, expected_reason: str) -> None:
    decision = evaluate_vacancy_policy(text)

    assert decision.allowed is False
    assert decision.reason == expected_reason
