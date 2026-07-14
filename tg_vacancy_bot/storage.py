from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from pathlib import Path

from .models import OperatorProfile, Vacancy


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
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            resume_text=row["resume_text"],
        )
