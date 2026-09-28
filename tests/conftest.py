"""Test-session hermeticity for file-based settings.

``Settings`` loads ``.env`` from the repository root, so a developer's local
configuration (enabled sources, keys, provider lists) would leak into tests
that construct ``Settings`` without those values. Pointing the dotenv source
at a nonexistent file keeps every other source working: explicit constructor
kwargs and real environment variables still apply, while default assertions
keep testing the true code defaults instead of the local ``.env``.
"""

from __future__ import annotations

import pytest

from tg_vacancy_bot.config import Settings


@pytest.fixture(autouse=True)
def _isolate_settings_from_local_env(monkeypatch):
    monkeypatch.setitem(Settings.model_config, "env_file", ".env.test-missing")
