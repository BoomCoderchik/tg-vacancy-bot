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

NONJUNIOR_SENIORITY_FOR_ROLE_RE = re.compile(
    r"(?<!\w)"
    r"(senior|middle|mid-level|mid\b|lead\b|principal|staff\b|сеньор\w*|миддл\w*|мидл\w*|ведущ\w+)"
    r"\W{0,5}"
    r"(?=front[\s-]?end\b|frontends?\b|full[\s-]?stack\b|fullstacks?\b|фронтенд|фул[\s-]?стек)",
    re.IGNORECASE,
)

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


def evaluate_vacancy_policy(text: str) -> VacancyPolicyDecision:
    """Apply the channel policy: only posts that really seek Junior Frontend/Fullstack developers.

    The post must contain a hiring signal, explicit frontend or fullstack role
    evidence, and a junior or entry-level marker. Posts advertising courses,
    mentorship, or a non-junior seniority level attached to the role are
    rejected with a diagnostic reason.
    """

    normalized = " ".join((text or "").split())
    if EXCLUDED_CONTEXT_RE.search(normalized):
        return VacancyPolicyDecision(False, "excluded_context")
    if not (FRONTEND_ROLE_RE.search(normalized) or FULLSTACK_ROLE_RE.search(normalized)):
        return VacancyPolicyDecision(False, "no_frontend_fullstack_role")
    if not JUNIOR_LEVEL_RE.search(normalized):
        return VacancyPolicyDecision(False, "no_junior_level_evidence")
    if NONJUNIOR_SENIORITY_FOR_ROLE_RE.search(normalized):
        return VacancyPolicyDecision(False, "non_junior_seniority_for_role")
    if not HIRING_INTENT_RE.search(normalized):
        return VacancyPolicyDecision(False, "no_hiring_intent")
    return VacancyPolicyDecision(True, "")


def filter_it_vacancies(vacancies: Iterable[Vacancy]) -> list[Vacancy]:
    """Keep only vacancies matching the unified Junior Frontend/Fullstack policy."""

    return [
        vacancy
        for vacancy in vacancies
        if evaluate_vacancy_policy(" ".join([vacancy.title, vacancy.description])).allowed
    ]
