from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

from .models import Vacancy


class VacancyStore:
    def __init__(self, database_path: str) -> None:
        self.database_path = database_path
        Path(database_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.database_path)

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
