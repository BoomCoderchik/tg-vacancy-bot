from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from tg_vacancy_bot.models import Vacancy


HIRING_INTENT_RE = re.compile(
    r"(?<!\w)("
    r"hiring|we\s+hire|hires\b|"
    r"(?:we\s+are|we'?re|i'?m)\s+looking\s+for|looking\s+for|"
    r"seeking|searching\s+for|"
    r"join\s+(?:our|my|the)\s+team|join\s+us|"
    r"open\s+(?:role|position|vacancy)|new\s+(?:vacancy|role)|job\s+opening|"
    r"vacanc\w+|apply\s+now|dm\s+me|send\s+(?:us\s+|your\s+)?(?:cv|resume)|(?:cv|resume)\s+to|"
    r"ищем|ищет\w*|нанима\w*|нанять|приглашаем|в\s+(?:нашу\s+)?команду|"
    r"вакансия\w*|требуется|требуются|нужен[аыи]?\b|розыск|открыт[аоы]\s+(?:роль|позиция|вакансия)"
    r")(?!\w)",
    re.IGNORECASE,
)

JUNIOR_LEVEL_RE = re.compile(
    r"(?<!\w)("
    r"juniors?|jr\.?|джуниор\w*|джун\w*|interns?\b|internship|trainees?|graduate\b|entry[\s-]?level|"
    r"no\s+experience|without\s+(?:commercial\s+)?experience|начинающ\w+|стаж[её]р\w*|стажировк\w*|"
    r"без\s+(?:коммерческого\s+)?опыта|минимальн\w+\s+опыт"
    r")(?!\w)",
    re.IGNORECASE,
)

FRONTEND_ROLE_RE = re.compile(
    r"\bfront[\s-]?ends?\b|\bfrontends?\b|\bфронт[\s-]?енд\w*|\bфронтендер\w*",
    re.IGNORECASE,
)
FULLSTACK_ROLE_RE = re.compile(
    r"\bfull[\s-]?stacks?\b|\bfullstacks?\b|\bфул{1,2}[\s-]?стек\w*",
    re.IGNORECASE,
)

BACKEND_ROLE_RE = re.compile(
    r"\bback[\s-]?ends?\b|\bbackends?\b|\bбэк[\s-]?енд\w*|\bбек[\s-]?енд\w*|\bбэкендер\w*|\bбекендер\w*",
    re.IGNORECASE,
)
MOBILE_ROLE_RE = re.compile(
    r"\bmobile\b|\bios\b|\bandroid\b|мобильн\w*|flutter|react\s*native|\bswift\b|\bkotlin\b",
    re.IGNORECASE,
)
QA_ROLE_RE = re.compile(
    r"(?<!\w)(qa|quality\s+assurance|tester|test\s+engineer|автотест\w*|тестиров\w+|тест[\s-]?инженер)(?!\w)",
    re.IGNORECASE,
)
DEVOPS_ROLE_RE = re.compile(
    r"devops|девопс|sre|site\s+reliability|platform\s+engineer|инфраструктур\w*|системн\w+\s+администратор",
    re.IGNORECASE,
)
DATA_ROLE_RE = re.compile(
    r"data\s+(?:scientist|engineer|analyst)|datascience|big\s+data|machine\s+learning|аналитик\w*|дата[-\s]?(?:сайентист|инженер|аналитик)",
    re.IGNORECASE,
)
DESIGN_ROLE_RE = re.compile(
    r"designer|дизайнер\w*|product\s+design|ux(?:/|$|\s)|(?<!\w)ui(?!\w)|figma|графическ\w+\s+дизайн",
    re.IGNORECASE,
)

SPECIALTY_PATTERNS: dict[str, re.Pattern[str]] = {
    "frontend": FRONTEND_ROLE_RE,
    "backend": BACKEND_ROLE_RE,
    "fullstack": FULLSTACK_ROLE_RE,
    "mobile": MOBILE_ROLE_RE,
    "qa": QA_ROLE_RE,
    "devops": DEVOPS_ROLE_RE,
    "data": DATA_ROLE_RE,
    "design": DESIGN_ROLE_RE,
}

VALID_SPECIALTIES: tuple[str, ...] = (
    "frontend",
    "backend",
    "fullstack",
    "frontend_fullstack",
    "mobile",
    "qa",
    "devops",
    "data",
    "design",
)
VALID_GRADES: tuple[str, ...] = ("intern", "junior", "middle", "senior", "lead")

DEFAULT_SPECIALTY = "frontend_fullstack"
DEFAULT_GRADE = "junior"

SPECIALTY_LABELS_RU: dict[str, str] = {
    "frontend": "Frontend",
    "backend": "Backend",
    "fullstack": "Fullstack",
    "frontend_fullstack": "Frontend+Fullstack",
    "mobile": "Mobile",
    "qa": "QA",
    "devops": "DevOps",
    "data": "Data",
    "design": "Design",
}
GRADE_LABELS_RU: dict[str, str] = {
    "intern": "Стажёр",
    "junior": "Junior",
    "middle": "Middle",
    "senior": "Senior",
    "lead": "Lead",
}

INTERN_LEVEL_RE = re.compile(
    r"(?<!\w)(interns?\b|internship|trainees?|стаж[её]р\w*|стажировк\w*)(?!\w)",
    re.IGNORECASE,
)
MIDDLE_LEVEL_RE = re.compile(
    r"(?<!\w)(middle|mid-level|mid\b|миддл\w*|мидл\w*)(?!\w)",
    re.IGNORECASE,
)
SENIOR_LEVEL_RE = re.compile(
    r"(?<!\w)(seniors?|сеньор\w*|синьор\w*)(?!\w)",
    re.IGNORECASE,
)
LEAD_LEVEL_RE = re.compile(
    r"(?<!\w)(lead\b|leads\b|principal|staff\b|тимлид\w*|ведущ\w+|руководитель\s+группы)(?!\w)",
    re.IGNORECASE,
)

GRADE_PATTERNS: dict[str, re.Pattern[str]] = {
    "intern": INTERN_LEVEL_RE,
    "junior": JUNIOR_LEVEL_RE,
    "middle": MIDDLE_LEVEL_RE,
    "senior": SENIOR_LEVEL_RE,
    "lead": LEAD_LEVEL_RE,
}

# Generic seniority-near-role guard used for grade-aware exclusions.
_ROLE_WORDS_FOR_EXCLUSION = (
    r"front[\s-]?end\b|frontends?\b|full[\s-]?stack\b|fullstacks?\b"
    r"|back[\s-]?end\b|backends?\b|mobile\b|ios\b|android\b"
    r"|qa\b|tester\b|devops\b|data\b|designer\b"
    r"|фронтенд|бэкенд|бекенд|фул[\s-]?стек|мобильн|тестиров|дизайнер|аналитик"
)
_HIGHER_SENIORITY_RE = re.compile(
    r"(?<!\w)"
    r"(senior|middle|mid-level|mid\b|lead\b|principal|staff\b|сеньор\w*|миддл\w*|мидл\w*|ведущ\w+|тимлид\w*)"
    r"\W{0,5}"
    rf"(?={_ROLE_WORDS_FOR_EXCLUSION})",
    re.IGNORECASE,
)
_SENIOR_LEAD_NEAR_ROLE_RE = re.compile(
    r"(?<!\w)"
    r"(senior|lead\b|principal|staff\b|сеньор\w*|ведущ\w+|тимлид\w*)"
    r"\W{0,5}"
    rf"(?={_ROLE_WORDS_FOR_EXCLUSION})",
    re.IGNORECASE,
)
_LEAD_NEAR_ROLE_RE = re.compile(
    r"(?<!\w)"
    r"(lead\b|principal|staff\b|ведущ\w+|тимлид\w*)"
    r"\W{0,5}"
    rf"(?={_ROLE_WORDS_FOR_EXCLUSION})",
    re.IGNORECASE,
)

NONJUNIOR_SENIORITY_FOR_ROLE_RE = _HIGHER_SENIORITY_RE


def normalize_specialty(value: str | None) -> str:
    normalized = (value or "").strip().lower()
    return normalized if normalized in VALID_SPECIALTIES else DEFAULT_SPECIALTY


def normalize_grade(value: str | None) -> str:
    normalized = (value or "").strip().lower()
    return normalized if normalized in VALID_GRADES else DEFAULT_GRADE


def specialty_matches(text: str, specialty: str) -> bool:
    if specialty == "frontend_fullstack":
        return bool(FRONTEND_ROLE_RE.search(text) or FULLSTACK_ROLE_RE.search(text))
    pattern = SPECIALTY_PATTERNS.get(specialty)
    return bool(pattern is not None and pattern.search(text))


def grade_matches(text: str, grade: str) -> bool:
    if grade == "junior":
        # Junior postings historically include intern/trainee/entry-level markers.
        return bool(JUNIOR_LEVEL_RE.search(text))
    pattern = GRADE_PATTERNS.get(grade)
    return bool(pattern is not None and pattern.search(text))


def excluded_seniority_for_grade(text: str, grade: str) -> bool:
    """Return True when a higher (or mismatched) seniority is attached to the role."""
    if grade in {"intern", "junior"}:
        return bool(_HIGHER_SENIORITY_RE.search(text))
    if grade == "middle":
        return bool(_SENIOR_LEAD_NEAR_ROLE_RE.search(text))
    if grade == "senior":
        return bool(_LEAD_NEAR_ROLE_RE.search(text))
    return False


EXCLUDED_CONTEXT_RE = re.compile(
    r"(?<!\w)("
    r"courses?\b|bootcamps?\b|webinars?\b|tutorials?\b|курс\w*|буткемп\w*|мастер[-\s]класс\w*|обучени\w*"
    r")(?!\w)|("
    r"looking\s+for\s+a\s+mentor|(?:need|want)s?\s+a\s+mentor|mentors?\s+(?:needed|wanted)|"
    r"ищ\w*\s+(?:ментора|наставника)|нужен\s+(?:ментор|наставник))"
    ,
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class VacancyPolicyDecision:
    """Result of the unified channel vacancy policy check."""

    allowed: bool
    reason: str


def evaluate_vacancy_policy(
    text: str,
    specialty: str | None = None,
    grade: str | None = None,
) -> VacancyPolicyDecision:
    """Apply the channel policy for the selected specialty and grade.

    Defaults preserve the historic Junior Frontend/Fullstack behaviour so
    existing callers and tests keep working. The post must contain a hiring
    signal, explicit role evidence for ``specialty``, and a level marker for
    ``grade``. Courses/mentorship and a mismatched seniority attached to the
    role are rejected with a diagnostic reason.
    """

    active_specialty = normalize_specialty(specialty) if specialty is not None else DEFAULT_SPECIALTY
    active_grade = normalize_grade(grade) if grade is not None else DEFAULT_GRADE
    is_default = active_specialty == DEFAULT_SPECIALTY and active_grade == DEFAULT_GRADE

    normalized = " ".join((text or "").split())
    if EXCLUDED_CONTEXT_RE.search(normalized):
        return VacancyPolicyDecision(False, "excluded_context")
    if not specialty_matches(normalized, active_specialty):
        if is_default:
            return VacancyPolicyDecision(False, "no_frontend_fullstack_role")
        return VacancyPolicyDecision(False, "no_specialty_role")
    if not grade_matches(normalized, active_grade):
        if is_default:
            return VacancyPolicyDecision(False, "no_junior_level_evidence")
        return VacancyPolicyDecision(False, "no_grade_evidence")
    if excluded_seniority_for_grade(normalized, active_grade):
        if is_default:
            return VacancyPolicyDecision(False, "non_junior_seniority_for_role")
        return VacancyPolicyDecision(False, "excluded_seniority_for_grade")
    if not HIRING_INTENT_RE.search(normalized):
        return VacancyPolicyDecision(False, "no_hiring_intent")
    return VacancyPolicyDecision(True, "")


def filter_it_vacancies(
    vacancies: Iterable[Vacancy],
    specialty: str | None = None,
    grade: str | None = None,
) -> list[Vacancy]:
    """Keep only vacancies matching the selected specialty/grade policy."""

    active_specialty = normalize_specialty(specialty) if specialty is not None else DEFAULT_SPECIALTY
    active_grade = normalize_grade(grade) if grade is not None else DEFAULT_GRADE
    return [
        vacancy
        for vacancy in vacancies
        if evaluate_vacancy_policy(
            " ".join([vacancy.title, vacancy.description]),
            active_specialty,
            active_grade,
        ).allowed
    ]
