from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4


SUPPORTED_RESUME_EXTENSIONS = frozenset({".pdf", ".docx"})


@dataclass(frozen=True)
class StoredResume:
    original_name: str
    stored_name: str


class ResumeStorage:
    """Local private storage for original resume files, outside Telegram and Git."""

    def __init__(self, directory: str, max_size_bytes: int) -> None:
        self.directory = Path(directory)
        self.max_size_bytes = max_size_bytes
        self.directory.mkdir(parents=True, exist_ok=True)

    def save(self, operator_user_id: int, original_name: str, content: bytes) -> StoredResume:
        safe_name = self._validate_upload(original_name, content)
        suffix = Path(safe_name).suffix.lower()
        stored_name = f"{operator_user_id}-{uuid4().hex}{suffix}"
        destination = self.directory / stored_name
        temporary = self.directory / f".{stored_name}.tmp"
        try:
            temporary.write_bytes(content)
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)
        return StoredResume(original_name=safe_name, stored_name=stored_name)

    def path_for(self, stored_name: str) -> Path:
        path = self.directory / Path(stored_name).name
        if path.name != stored_name or path.parent != self.directory:
            raise ValueError("Invalid stored resume name")
        return path

    def delete(self, stored_name: str) -> bool:
        path = self.path_for(stored_name)
        if not path.exists():
            return False
        path.unlink()
        return True

    def _validate_upload(self, original_name: str, content: bytes) -> str:
        name = Path(original_name).name
        if not original_name or name != original_name:
            raise ValueError("Resume filename must not contain a path")
        if Path(name).suffix.lower() not in SUPPORTED_RESUME_EXTENSIONS:
            raise ValueError("Resume must be a PDF or DOCX file")
        if not content:
            raise ValueError("Resume file is empty")
        if len(content) > self.max_size_bytes:
            raise ValueError("Resume file exceeds the configured size limit")
        return name
