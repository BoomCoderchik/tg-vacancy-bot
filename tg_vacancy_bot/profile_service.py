from __future__ import annotations

from dataclasses import replace

from .models import OperatorProfile
from .resume_storage import ResumeStorage
from .storage import VacancyStore


class ProfileService:
    """Coordinates private profile records and their local resume files."""

    def __init__(self, store: VacancyStore, resume_storage: ResumeStorage) -> None:
        self.store = store
        self.resume_storage = resume_storage

    def save_resume(self, operator_user_id: int, original_name: str, content: bytes) -> OperatorProfile:
        saved_resume = self.resume_storage.save(operator_user_id, original_name, content)
        profile = self.store.get_operator_profile(operator_user_id) or OperatorProfile(
            operator_user_id=operator_user_id
        )
        updated_profile = replace(
            profile,
            resume_original_name=saved_resume.original_name,
            resume_stored_name=saved_resume.stored_name,
            resume_text=None,
        )
        try:
            self.store.save_operator_profile(updated_profile)
        except Exception:
            self.resume_storage.delete(saved_resume.stored_name)
            raise
        if profile.resume_stored_name:
            self.resume_storage.delete(profile.resume_stored_name)
        return updated_profile

    def delete_profile(self, operator_user_id: int) -> bool:
        profile = self.store.get_operator_profile(operator_user_id)
        if profile is None:
            return False
        self.store.delete_operator_profile(operator_user_id)
        if profile.resume_stored_name:
            self.resume_storage.delete(profile.resume_stored_name)
        return True
