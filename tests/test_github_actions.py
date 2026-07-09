from pathlib import Path


WORKFLOW = Path(".github/workflows/poll-sources.yml")


def test_poll_sources_workflow_runs_every_15_minutes() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert 'cron: "7,22,37,52 * * * *"' in text
    assert "tg-vacancy-bot poll-once" in text
    assert "SOURCE_POLL_INTERVAL_SECONDS: \"0\"" in text
    assert "concurrency:" in text


def test_poll_sources_workflow_preserves_dedupe_state() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "actions/cache@v4" in text
    assert "path: data/" in text
    assert "DATABASE_PATH: data/vacancies.sqlite3" in text
    assert "key: vacancy-db-${{ github.run_id }}" in text
    assert "vacancy-db-" in text


def test_poll_sources_workflow_defaults_optional_runtime_values() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "SOURCE_MAX_PUBLISH_PER_POLL: ${{ secrets.SOURCE_MAX_PUBLISH_PER_POLL || '20' }}" in text
    assert "SOURCE_MAX_AGE_HOURS: ${{ secrets.SOURCE_MAX_AGE_HOURS || '48' }}" in text
    assert "LOCALIZE_DESCRIPTIONS: ${{ secrets.LOCALIZE_DESCRIPTIONS || 'false' }}" in text
    assert "ENABLE_JOBICY: ${{ secrets.ENABLE_JOBICY || 'true' }}" in text
    assert "ENABLE_JOBSPY_LINKEDIN: ${{ secrets.ENABLE_JOBSPY_LINKEDIN || 'false' }}" in text
    assert "LINKEDIN_POST_SEARCH_QUERY: ${{ secrets.LINKEDIN_POST_SEARCH_QUERY ||" in text
    assert "LINKEDIN_POST_SCRAPER_QUERY: ${{ secrets.LINKEDIN_POST_SCRAPER_QUERY ||" in text
    assert "JOBSPY_LINKEDIN_QUERY: ${{ secrets.JOBSPY_LINKEDIN_QUERY ||" in text
