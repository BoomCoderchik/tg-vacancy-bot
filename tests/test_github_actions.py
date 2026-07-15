from pathlib import Path


WORKFLOW = Path(".github/workflows/scheduled-source-polling.yml")
OLD_WORKFLOW = Path(".github/workflows/poll-sources.yml")


def test_poll_sources_workflow_runs_every_15_minutes() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert not OLD_WORKFLOW.exists()
    assert 'cron: "7 * * * *"' in text
    assert 'cron: "22 * * * *"' in text
    assert 'cron: "37 * * * *"' in text
    assert 'cron: "52 * * * *"' in text
    assert "tg-vacancy-bot poll-once" in text
    assert "SOURCE_POLL_INTERVAL_SECONDS: \"0\"" in text
    assert "concurrency:" in text


def test_poll_sources_workflow_preserves_dedupe_state() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "actions/cache@v5" in text
    assert "path: data/" in text
    assert "DATABASE_PATH: data/vacancies.sqlite3" in text
    assert "key: vacancy-db-${{ github.run_id }}" in text
    assert "vacancy-db-" in text


def test_poll_sources_workflow_defaults_optional_runtime_values() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "SOURCE_MAX_PUBLISH_PER_POLL: ${{ secrets.SOURCE_MAX_PUBLISH_PER_POLL || '20' }}" in text
    assert "SOURCE_MAX_AGE_HOURS: ${{ secrets.SOURCE_MAX_AGE_HOURS || '48' }}" in text
    assert 'ENABLE_ARBEITNOW: "true"' in text
    assert 'LOCALIZE_DESCRIPTIONS: "false"' in text
    assert "ENABLE_LINKEDIN_POST_HEADLESS: ${{ secrets.ENABLE_LINKEDIN_POST_HEADLESS || 'false' }}" in text
    assert "ENABLE_LINKEDIN_POST_SCRAPER: ${{ secrets.ENABLE_LINKEDIN_POST_SCRAPER || 'true' }}" in text
    assert "SERPER_API_KEY: ${{ secrets.SERPER_API_KEY }}" in text
    assert "LINKEDIN_POST_SEARCH_QUERY: ${{ secrets.LINKEDIN_POST_SEARCH_QUERY ||" in text
    assert "LINKEDIN_POST_SCRAPER_QUERY: ${{ secrets.LINKEDIN_POST_SCRAPER_QUERY ||" in text
    assert "python -m playwright install --with-deps chromium" in text
