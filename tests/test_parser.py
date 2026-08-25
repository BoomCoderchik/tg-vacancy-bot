from tg_vacancy_bot.parser import (
    extract_labeled_fields,
    extract_stack,
    guess_location,
    guess_salary,
    guess_title,
    parse_message_to_vacancy,
)


def test_parse_forwarded_linkedin_message() -> None:
    text = """
Senior Full-Stack Engineer
Локация: Удаленно (США)
Стек: Python, FastAPI, React, AWS, PostgreSQL

Компания ищет Senior Full-Stack Engineer для AI-платформы.
https://www.linkedin.com/posts/example
"""

    vacancy = parse_message_to_vacancy(text)

    assert vacancy.title == "Senior Full-Stack Engineer"
    assert vacancy.location == "Удаленно (США)"
    assert vacancy.source == "LinkedIn"
    assert vacancy.url == "https://www.linkedin.com/posts/example"
    assert "Python" in vacancy.stack
    assert "React" in vacancy.stack


def test_extract_stack_keeps_known_order() -> None:
    stack = extract_stack("Need React, Python, AWS, Docker and PostgreSQL")

    assert stack == ("Python", "React", "PostgreSQL", "AWS", "Docker")


def test_extract_stack_requires_word_boundaries() -> None:
    assert extract_stack("Innovation at Google scale, good category") == ()
    assert "AI" not in extract_stack("Contact us by email or check the html page")
    assert "ML" not in extract_stack("Send the html template by email")


def test_extract_stack_does_not_add_java_for_javascript() -> None:
    stack = extract_stack("Strong JavaScript skills required")

    assert stack == ("JavaScript",)
    assert "Java" not in stack
    assert extract_stack("Legacy services on Java") == ("Java",)


def test_extract_stack_matches_special_tokens_exactly() -> None:
    stack = extract_stack("c#, asp.net, node.js and next.js roles")

    assert stack == ("Next.js", "Node.js", "C#")


def test_guess_location_respects_word_boundaries() -> None:
    assert guess_location("Our team in Russia grows since August") is None
    assert guess_location("Remote work only") == "Удаленно"
    assert guess_location("Office in Germany") == "Germany"


def test_guess_salary_parses_russian_ranges() -> None:
    assert guess_salary("Зарплата: от 1000 до 2000 $") == "от 1000 до 2000 $"
    assert guess_salary("от 1000$ до 2500$") == "от 1000$ до 2500$"


def test_guess_salary_parses_russian_thousand_markers() -> None:
    assert guess_salary("оклад 120к руб") == "120к руб"
    assert guess_salary("150 тыс руб на руки") == "150 тыс руб"


def test_guess_salary_ignores_years_and_phone_numbers() -> None:
    assert guess_salary("Founded in 2024") is None
    assert guess_salary("Call +7 999 123-45-67") is None


def test_guess_salary_keeps_existing_formats() -> None:
    assert guess_salary("Salary $5000 - $7000") == "$5000 - $7000"
    assert guess_salary("Rate 5000 usd") == "5000 usd"
    assert guess_salary("Budget 300 000 ₽") == "300 000 ₽"


def test_guess_title_skips_bare_role_fragments_for_later_candidates() -> None:
    title = guess_title("developer\nSenior Python Developer in fintech team")

    assert title == "Senior Python Developer in fintech team"
    assert guess_title("qa\nJoin our supportive product team") == "Join our supportive product team"


def test_extract_labeled_fields_supports_card_style_lines() -> None:
    fields = extract_labeled_fields(
        """
💼 Senior Full-Stack Engineer
📍 Локация: Удаленно (США)
🧠 Стек: Python, FastAPI, React
💰 Зарплата: $5000 - $7000
🏢 Компания: Example AI
"""
    )

    assert fields == {
        "location": "Удаленно (США)",
        "stack": "Python, FastAPI, React",
        "salary": "$5000 - $7000",
        "company": "Example AI",
    }


def test_parse_labeled_card_keeps_description_clean() -> None:
    text = """
Senior Full-Stack Engineer
Компания: Example AI
Location: Remote US
Stack: Python, FastAPI, React, PostgreSQL
Salary: $5000 - $7000

Description:
Build backend and frontend features for an AI platform.
https://www.linkedin.com/posts/example
"""

    vacancy = parse_message_to_vacancy(text)

    assert vacancy.title == "Senior Full-Stack Engineer"
    assert vacancy.company == "Example AI"
    assert vacancy.location == "Remote US"
    assert vacancy.salary == "$5000 - $7000"
    assert vacancy.stack[:4] == ("Python", "FastAPI", "React", "PostgreSQL")
    assert vacancy.description == "Build backend and frontend features for an AI platform."
    assert "Stack:" not in vacancy.description
    assert "Location:" not in vacancy.description


def test_parse_labeled_card_does_not_treat_title_hyphen_as_label() -> None:
    text = """
Senior Full-Stack Engineer
Location: Remote
Stack: Python, React

Description:
Build product features.
"""

    vacancy = parse_message_to_vacancy(text)

    assert vacancy.title == "Senior Full-Stack Engineer"
    assert vacancy.description == "Build product features."


def test_parse_message_extracts_stack_from_explicit_description_evidence() -> None:
    text = """
Senior Backend Engineer
Location: Remote

Description:
Build Python APIs and React admin screens for a fintech platform.
"""

    vacancy = parse_message_to_vacancy(text)

    assert vacancy.stack == ("Python", "React")


def test_parse_message_without_stack_evidence_keeps_stack_empty() -> None:
    text = """
Senior Backend Engineer
Location: Remote

Description:
Build product features for an AI software platform.
"""

    vacancy = parse_message_to_vacancy(text)

    assert vacancy.stack == ()


def test_parse_message_with_explicit_stack_uses_only_stack_field() -> None:
    text = """
Senior Backend Engineer
Location: Remote
Stack: Python, FastAPI

Description:
Build services that deploy to AWS and store data in PostgreSQL.
"""

    vacancy = parse_message_to_vacancy(text)

    assert vacancy.stack == ("Python", "FastAPI")
