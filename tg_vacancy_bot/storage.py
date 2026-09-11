from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

from .models import Application, ApplicationStatus, OperatorProfile, Vacancy, VacancyFilter


class VacancyStore:
    def __init__(self, database_path: str) -> None:
        self.database_path = database_path
        Path(database_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS published_vacancies (
                    fingerprint TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    source TEXT NOT NULL,
                    url TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            self._apply_profile_migration(conn)
            self._apply_application_migration(conn)
            self._apply_queue_resume_migration(conn)
            self._apply_vacancy_filter_migration(conn)
            self._apply_vacancy_filter_list_migration(conn)

    @staticmethod
    def _apply_profile_migration(conn: sqlite3.Connection) -> None:
        version = 1
        applied = conn.execute(
            "SELECT 1 FROM schema_migrations WHERE version = ?", (version,)
        ).fetchone()
        if applied:
            return

        conn.execute(
            """
            CREATE TABLE operator_profiles (
                operator_user_id INTEGER PRIMARY KEY,
                full_name TEXT,
                email TEXT,
                phone TEXT,
                desired_salary TEXT,
                location TEXT,
                work_format TEXT,
                employment_type TEXT,
                extra_fields_json TEXT NOT NULL DEFAULT '{}',
                resume_original_name TEXT,
                resume_stored_name TEXT,
                resume_text TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute("INSERT INTO schema_migrations (version) VALUES (?)", (version,))

    @staticmethod
    def _apply_application_migration(conn: sqlite3.Connection) -> None:
        version = 2
        if conn.execute("SELECT 1 FROM schema_migrations WHERE version = ?", (version,)).fetchone():
            return
        conn.execute(
            """
            CREATE TABLE applications (
                application_id TEXT PRIMARY KEY,
                operator_user_id INTEGER NOT NULL,
                vacancy_fingerprint TEXT NOT NULL,
                vacancy_url TEXT,
                site TEXT,
                status TEXT NOT NULL,
                form_fields_json TEXT NOT NULL DEFAULT '[]',
                filled_values_json TEXT NOT NULL DEFAULT '{}',
                missing_fields_json TEXT NOT NULL DEFAULT '[]',
                error_description TEXT,
                submission_result TEXT,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(operator_user_id, vacancy_fingerprint)
            )
            """
        )
        conn.execute("INSERT INTO schema_migrations (version) VALUES (?)", (version,))

    @staticmethod
    def _apply_queue_resume_migration(conn: sqlite3.Connection) -> None:
        version = 3
        if conn.execute("SELECT 1 FROM schema_migrations WHERE version = ?", (version,)).fetchone():
            return
        conn.execute("ALTER TABLE operator_profiles ADD COLUMN resume_telegram_file_id TEXT")
        conn.execute("INSERT INTO schema_migrations (version) VALUES (?)", (version,))

    @staticmethod
    def _apply_vacancy_filter_migration(conn: sqlite3.Connection) -> None:
        version = 4
        if conn.execute("SELECT 1 FROM schema_migrations WHERE version = ?", (version,)).fetchone():
            return
        conn.execute(
            """
            CREATE TABLE vacancy_filters (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                specialty TEXT NOT NULL DEFAULT 'frontend_fullstack',
                grade TEXT NOT NULL DEFAULT 'junior',
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.execute(
            "INSERT OR IGNORE INTO vacancy_filters (id, specialty, grade) VALUES (1, 'frontend_fullstack', 'junior')"
        )
        conn.execute("INSERT INTO schema_migrations (version) VALUES (?)", (version,))

    @staticmethod
    def _apply_vacancy_filter_list_migration(conn: sqlite3.Connection) -> None:
        version = 5
        if conn.execute("SELECT 1 FROM schema_migrations WHERE version = ?", (version,)).fetchone():
            return
        conn.execute("ALTER TABLE vacancy_filters ADD COLUMN specialties_json TEXT")
        conn.execute("ALTER TABLE vacancy_filters ADD COLUMN grades_json TEXT")
        for row in conn.execute("SELECT id, specialty, grade FROM vacancy_filters").fetchall():
            specialties_json = json.dumps([row["specialty"] or "frontend_fullstack"])
            grades_json = json.dumps([row["grade"] or "junior"])
            conn.execute(
                "UPDATE vacancy_filters SET specialties_json = ?, grades_json = ? WHERE id = ?",
                (specialties_json, grades_json, row["id"]),
            )
        conn.execute("INSERT INTO schema_migrations (version) VALUES (?)", (version,))

    @staticmethod
    def fingerprint(vacancy: Vacancy) -> str:
        digest = hashlib.sha256(vacancy.identity_source.encode("utf-8")).hexdigest()
        return digest[:32]

    def seen(self, vacancy: Vacancy) -> bool:
        fingerprint = self.fingerprint(vacancy)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM published_vacancies WHERE fingerprint = ?",
                (fingerprint,),
            ).fetchone()
        return row is not None

    def mark_published(self, vacancy: Vacancy) -> bool:
        fingerprint = self.fingerprint(vacancy)
        with self._connect() as conn:
            try:
                conn.execute(
                    "INSERT INTO published_vacancies (fingerprint, title, source, url) VALUES (?, ?, ?, ?)",
                    (fingerprint, vacancy.title, vacancy.source, vacancy.url),
                )
                return True
            except sqlite3.IntegrityError:
                return False

    def published_vacancy_url(self, vacancy_id: str) -> str | None:
        """Resolve the short callback identifier without accepting arbitrary SQL input."""
        if not re.fullmatch(r"[0-9a-f]{32}", vacancy_id):
            return None
        with self._connect() as conn:
            row = conn.execute(
                "SELECT url FROM published_vacancies WHERE fingerprint = ?", (vacancy_id,)
            ).fetchone()
        return row["url"] if row else None

    def get_vacancy_filter(self) -> VacancyFilter:
        """Return the global specialties/grades filter, falling back to defaults."""
        from .sources.filters import (
            DEFAULT_GRADE,
            DEFAULT_SPECIALTY,
            normalize_grades,
            normalize_specialties,
        )

        with self._connect() as conn:
            try:
                row = conn.execute("SELECT * FROM vacancy_filters WHERE id = 1").fetchone()
            except sqlite3.OperationalError:
                return VacancyFilter()
        if row is None:
            return VacancyFilter()
        try:
            stored_specialties = json.loads(row["specialties_json"])
            stored_grades = json.loads(row["grades_json"])
        except (TypeError, ValueError, KeyError, IndexError):
            stored_specialties = [row["specialty"]]
            stored_grades = [row["grade"]]
        if not isinstance(stored_specialties, list) or not stored_specialties:
            stored_specialties = [DEFAULT_SPECIALTY]
        if not isinstance(stored_grades, list) or not stored_grades:
            stored_grades = [DEFAULT_GRADE]
        return VacancyFilter(
            specialties=tuple(normalize_specialties(stored_specialties)),
            grades=tuple(normalize_grades(stored_grades)),
        )

    def set_vacancy_filter(
        self,
        specialties: str | list[str] | tuple[str, ...],
        grades: str | list[str] | tuple[str, ...],
    ) -> VacancyFilter:
        """Persist the global specialties/grades filter after validating values."""
        from .sources.filters import VALID_GRADES, VALID_SPECIALTIES

        raw_specialties = [specialties] if isinstance(specialties, str) else list(specialties)
        raw_grades = [grades] if isinstance(grades, str) else list(grades)
        cleaned_specialties = [item.strip().lower() for item in raw_specialties if item.strip()]
        cleaned_grades = [item.strip().lower() for item in raw_grades if item.strip()]
        unknown_specialties = [item for item in cleaned_specialties if item not in VALID_SPECIALTIES]
        unknown_grades = [item for item in cleaned_grades if item not in VALID_GRADES]
        if unknown_specialties:
            raise ValueError(f"Unknown specialties: {', '.join(unknown_specialties)}")
        if unknown_grades:
            raise ValueError(f"Unknown grades: {', '.join(unknown_grades)}")
        if not cleaned_specialties:
            raise ValueError("Select at least one specialty")
        if not cleaned_grades:
            raise ValueError("Select at least one grade")
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO vacancy_filters (id, specialty, grade, specialties_json, grades_json, updated_at)
                VALUES (1, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(id) DO UPDATE SET
                    specialty = excluded.specialty,
                    grade = excluded.grade,
                    specialties_json = excluded.specialties_json,
                    grades_json = excluded.grades_json,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    cleaned_specialties[0],
                    cleaned_grades[0],
                    json.dumps(cleaned_specialties),
                    json.dumps(cleaned_grades),
                ),
            )
        return VacancyFilter(specialties=tuple(cleaned_specialties), grades=tuple(cleaned_grades))

    def application_queue_counts(self) -> tuple[int, int]:
        """Return non-sensitive queue counters for operational diagnostics."""
        with self._connect() as conn:
            published = conn.execute("SELECT COUNT(*) FROM published_vacancies").fetchone()[0]
            applications = conn.execute("SELECT COUNT(*) FROM applications").fetchone()[0]
        return int(published), int(applications)

    def create_application(self, operator_user_id: int, vacancy_id: str) -> tuple[Application, bool] | None:
        if not re.fullmatch(r"[0-9a-f]{32}", vacancy_id):
            return None
        with self._connect() as conn:
            vacancy = conn.execute(
                "SELECT url FROM published_vacancies WHERE fingerprint = ?", (vacancy_id,)
            ).fetchone()
            if vacancy is None:
                return None
            existing = conn.execute(
                "SELECT * FROM applications WHERE operator_user_id = ? AND vacancy_fingerprint = ?",
                (operator_user_id, vacancy_id),
            ).fetchone()
            if existing:
                return self._application_from_row(existing), False
            url = vacancy["url"]
            status: ApplicationStatus = "created" if url else "failed"
            error = None if url else "Vacancy does not contain an external application URL."
            site = urlparse(url).netloc.lower() if url else None
            application_id = uuid4().hex[:16]
            conn.execute(
                """INSERT INTO applications (application_id, operator_user_id, vacancy_fingerprint, vacancy_url, site, status, error_description)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (application_id, operator_user_id, vacancy_id, url, site, status, error),
            )
            row = conn.execute("SELECT * FROM applications WHERE application_id = ?", (application_id,)).fetchone()
        return self._application_from_row(row), True

    def update_application_status(self, application_id: str, status: ApplicationStatus, error: str | None = None) -> bool:
        with self._connect() as conn:
            result = conn.execute(
                "UPDATE applications SET status = ?, error_description = ?, updated_at = CURRENT_TIMESTAMP WHERE application_id = ?",
                (status, error, application_id),
            )
        return result.rowcount == 1

    def get_operator_profile(self, operator_user_id: int) -> OperatorProfile | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM operator_profiles WHERE operator_user_id = ?", (operator_user_id,)
            ).fetchone()
        return self._profile_from_row(row) if row else None

    def save_operator_profile(self, profile: OperatorProfile) -> None:
        if not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in profile.extra_fields.items()
        ):
            raise ValueError("Operator profile extra fields must be string pairs")
        extra_fields_json = json.dumps(profile.extra_fields, ensure_ascii=False, sort_keys=True)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO operator_profiles (
                    operator_user_id, full_name, email, phone, desired_salary, location,
                    work_format, employment_type, extra_fields_json, resume_original_name,
                    resume_stored_name, resume_text
                    , resume_telegram_file_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(operator_user_id) DO UPDATE SET
                    full_name = excluded.full_name,
                    email = excluded.email,
                    phone = excluded.phone,
                    desired_salary = excluded.desired_salary,
                    location = excluded.location,
                    work_format = excluded.work_format,
                    employment_type = excluded.employment_type,
                    extra_fields_json = excluded.extra_fields_json,
                    resume_original_name = excluded.resume_original_name,
                    resume_stored_name = excluded.resume_stored_name,
                    resume_telegram_file_id = excluded.resume_telegram_file_id,
                    resume_text = excluded.resume_text,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    profile.operator_user_id,
                    profile.full_name,
                    profile.email,
                    profile.phone,
                    profile.desired_salary,
                    profile.location,
                    profile.work_format,
                    profile.employment_type,
                    extra_fields_json,
                    profile.resume_original_name,
                    profile.resume_stored_name,
                    profile.resume_text,
                    profile.resume_telegram_file_id,
                ),
            )

    def delete_operator_profile(self, operator_user_id: int) -> bool:
        with self._connect() as conn:
            result = conn.execute(
                "DELETE FROM operator_profiles WHERE operator_user_id = ?", (operator_user_id,)
            )
        return result.rowcount == 1

    @staticmethod
    def _profile_from_row(row: sqlite3.Row) -> OperatorProfile:
        extra_fields = json.loads(row["extra_fields_json"])
        if not isinstance(extra_fields, dict) or not all(
            isinstance(key, str) and isinstance(value, str) for key, value in extra_fields.items()
        ):
            raise ValueError("Stored operator profile has invalid extra fields")
        return OperatorProfile(
            operator_user_id=row["operator_user_id"],
            full_name=row["full_name"],
            email=row["email"],
            phone=row["phone"],
            desired_salary=row["desired_salary"],
            location=row["location"],
            work_format=row["work_format"],
            employment_type=row["employment_type"],
            extra_fields=extra_fields,
            resume_original_name=row["resume_original_name"],
            resume_stored_name=row["resume_stored_name"],
            resume_telegram_file_id=row["resume_telegram_file_id"],
            resume_text=row["resume_text"],
        )

    @staticmethod
    def _application_from_row(row: sqlite3.Row) -> Application:
        return Application(
            application_id=row["application_id"], operator_user_id=row["operator_user_id"],
            vacancy_fingerprint=row["vacancy_fingerprint"], vacancy_url=row["vacancy_url"],
            site=row["site"], status=row["status"], error_description=row["error_description"],
        )
