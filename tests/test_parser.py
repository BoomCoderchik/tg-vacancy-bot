from tg_vacancy_bot.parser import extract_stack, parse_message_to_vacancy


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
