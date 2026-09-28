"""Test-session hermeticity for file-based and runner-provided settings.

``Settings`` loads ``.env`` from the repository root, so a developer's local
configuration (enabled sources, keys, provider lists) would leak into tests
that construct ``Settings`` without those values. Pointing the dotenv source
at a nonexistent file keeps every other source working: explicit constructor
kwargs and real environment variables still apply, while default assertions
keep testing the true code defaults instead of the local ``.env``.

CI runners add a second leak: GitHub Actions exports ``GITHUB_REPOSITORY``
(and similar ``GITHUB_*`` variables) into every job, and ``Settings`` reads
``GITHUB_REPOSITORY`` for the filter-sync feature. Tests that expect "no
repository configured" would therefore pass locally and fail on GitHub. Those
runner-provided variables are removed for the duration of each test; tests
that need them set them explicitly.
"""

from __future__ import annotations

import pytest

from tg_vacancy_bot.config import Settings

# Environment variables that CI runners define for their own purposes but that
# collide with ``Settings`` aliases. Keep in sync with ``tg_vacancy_bot/config.py``.
RUNNER_PROVIDED_SETTINGS_ENV = (
    "GITHUB_REPOSITORY",
    "GITHUB_FILTER_SYNC_TOKEN",
)


@pytest.fixture(autouse=True)
def _isolate_settings_from_local_env(monkeypatch):
    monkeypatch.setitem(Settings.model_config, "env_file", ".env.test-missing")
    for name in RUNNER_PROVIDED_SETTINGS_ENV:
        monkeypatch.delenv(name, raising=False)
