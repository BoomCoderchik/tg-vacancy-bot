from tg_vacancy_bot.parser import extract_labeled_fields, extract_stack, parse_message_to_vacancy


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
