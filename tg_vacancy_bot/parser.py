from __future__ import annotations

import re
from urllib.parse import urlparse

from .models import Vacancy


URL_RE = re.compile(r"https?://[^\s<>)\"']+", re.IGNORECASE)

TECH_KEYWORDS = [
    "Python",
    "FastAPI",
    "Django",
    "Flask",
    "JavaScript",
    "TypeScript",
    "React",
    "Next.js",
    "Vue",
    "Angular",
    "Node.js",
    "NestJS",
    "Go",
    "Golang",
    "Java",
    "Kotlin",
    "Spring",
    "C#",
    ".NET",
    "PHP",
    "Laravel",
    "Ruby",
    "Rails",
    "Rust",
    "SQL",
    "PostgreSQL",
    "MySQL",
    "MongoDB",
    "Redis",
    "AWS",
    "GCP",
    "Azure",
    "Docker",
    "Kubernetes",
    "Terraform",
    "DevOps",
    "QA",
    "Selenium",
    "Cypress",
    "Playwright",
    "AI",
    "ML",
    "LLM",
]

TITLE_HINT_RE = re.compile(
    r"(?P<title>(senior|middle|junior|lead|staff|principal)?\s*"
    r"[\w+#./ -]{0,40}(developer|engineer|devops|qa|designer|analyst|architect|разработчик|инженер|тестировщик)"
    r"[\w+#./ -]{0,50})",
    re.IGNORECASE,
)

LOCATION_RE = re.compile(
    r"(remote|удаленн?о|удалённ?о|hybrid|onsite|relocation|europe|usa|us|uk|germany|poland|cyprus|serbia|armenia|georgia|казахстан|европа|сша)",
    re.IGNORECASE,
)

SALARY_RE = re.compile(
    r"((?:\$|€|£)\s?\d[\d\s,.]*(?:\s?-\s?(?:\$|€|£)?\s?\d[\d\s,.]*)?|"
    r"\d[\d\s,.]*\s?(?:usd|eur|gbp|rub|₽|k|тыс\.?)(?:\s?-\s?\d[\d\s,.]*\s?(?:usd|eur|gbp|rub|₽|k|тыс\.?))?)",
    re.IGNORECASE,
)

FIELD_LABELS = {
    "location": ("location", "локация", "локации", "место", "формат"),
    "stack": ("stack", "стек", "технологии", "skills", "tech stack"),
    "salary": ("salary", "зарплата", "вилка", "compensation", "rate"),
    "company": ("company", "компания"),
}

LABEL_RE = re.compile(r"^\s*(?:[^\wа-яА-ЯёЁ$€£₽]+)?(?P<label>[\wа-яА-ЯёЁ ]{2,24})\s*[:：-]\s*(?P<value>.+?)\s*$", re.IGNORECASE)


def extract_urls(text: str) -> list[str]:
    urls = [url.rstrip(".,;") for url in URL_RE.findall(text or "")]
    seen: set[str] = set()
    result: list[str] = []
    for url in urls:
        if url not in seen:
            seen.add(url)
            result.append(url)
    return result


def extract_stack(text: str) -> tuple[str, ...]:
    found: list[str] = []
    lower = text.lower()
    for item in TECH_KEYWORDS:
        if item.lower() in lower and item not in found:
            found.append(item)
    sql_specific = {"PostgreSQL", "MySQL"}
    if "SQL" in found and any(item in found for item in sql_specific):
        found.remove("SQL")
    return tuple(found)


def extract_labeled_fields(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in text.splitlines():
        match = LABEL_RE.match(line)
        if not match:
            continue
        label = " ".join(match.group("label").lower().split())
        value = match.group("value").strip()
        for field_name, aliases in FIELD_LABELS.items():
            if label in aliases and value:
                fields.setdefault(field_name, value[:500])
                break
    return fields


def remove_labeled_lines(text: str) -> str:
    kept = []
    for line in text.splitlines():
        if LABEL_RE.match(line):
            continue
        kept.append(line)
    return "\n".join(kept).strip()


def guess_title(text: str) -> str:
    lines = [line.strip(" -•\t") for line in text.splitlines() if line.strip()]
    for line in lines[:8]:
        if len(line) <= 90 and TITLE_HINT_RE.search(line):
            return line

    match = TITLE_HINT_RE.search(text)
    if match:
        return " ".join(match.group("title").split())

    for line in lines[:5]:
        if 8 <= len(line) <= 90:
            return line

    return "IT Vacancy"


def guess_location(text: str) -> str | None:
    for line in text.splitlines():
        if "локац" in line.lower() or "location" in line.lower():
            value = re.sub(r"^\s*(📍)?\s*(локация|location)\s*:?\s*", "", line, flags=re.IGNORECASE)
            return value.strip()[:120] or None

    match = LOCATION_RE.search(text)
    if match:
        value = match.group(0)
        if value.lower() in {"remote", "удаленно", "удалённо"}:
            return "Удаленно"
        return value
    return None


def parse_stack_value(value: str) -> tuple[str, ...]:
    parts = [part.strip(" •,;") for part in re.split(r"[,;/|]+", value) if part.strip(" •,;")]
    if not parts:
        return extract_stack(value)

    known = extract_stack(value)
    combined = [*parts, *known]
    result: list[str] = []
    for item in combined:
        if item and item not in result:
            result.append(item)
    return tuple(result)


def guess_salary(text: str) -> str | None:
    match = SALARY_RE.search(text)
    if not match:
        return None
    return " ".join(match.group(0).split())


def detect_source(url: str | None) -> str:
    if not url:
        return "Telegram"
    host = urlparse(url).netloc.lower().removeprefix("www.")
    if "linkedin.com" in host:
        return "LinkedIn"
    if "t.me" in host or "telegram.me" in host:
        return "Telegram"
    return host or "External"


def parse_message_to_vacancy(text: str, fallback_source: str = "Telegram") -> Vacancy:
    cleaned = (text or "").strip()
    urls = extract_urls(cleaned)
    primary_url = urls[0] if urls else None
    source = detect_source(primary_url) if primary_url else fallback_source

    without_urls = URL_RE.sub("", cleaned).strip()
    labeled_fields = extract_labeled_fields(without_urls)
    title = guess_title(without_urls or cleaned)
    location = labeled_fields.get("location") or guess_location(without_urls)
    salary = labeled_fields.get("salary") or guess_salary(without_urls)
    stack = parse_stack_value(labeled_fields["stack"]) if "stack" in labeled_fields else extract_stack(without_urls)
    description = remove_labeled_lines(without_urls)

    if description.startswith(title):
        description = description[len(title) :].strip(" \n:-")

    return Vacancy(
        title=title,
        description=description or cleaned,
        source=source,
        url=primary_url,
        location=location,
        company=labeled_fields.get("company"),
        stack=stack,
        salary=salary,
        raw_text=cleaned,
    )
