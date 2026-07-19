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
    assert "tg-vacancy-bot process-applications-once" in text
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
    assert 'ENABLE_WORKING_NOMADS: "true"' in text
    assert 'LOCALIZE_DESCRIPTIONS: "true"' in text
    assert "LOCALIZATION_PROVIDER: ${{ secrets.LOCALIZATION_PROVIDER || 'openai' }}" in text
    assert "OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}" in text
    assert "GROQ_API_KEY: ${{ secrets.GROQ_API_KEY }}" in text
    assert "Verify required localization configuration" not in text
    assert "ENABLE_LINKEDIN_POST_HEADLESS: ${{ secrets.ENABLE_LINKEDIN_POST_HEADLESS || 'false' }}" in text
    assert "ENABLE_LINKEDIN_POST_SCRAPER: ${{ secrets.ENABLE_LINKEDIN_POST_SCRAPER || 'false' }}" in text
    assert "LINKEDIN_HEADLESS_ACCESS_AUTHORIZED: ${{ secrets.LINKEDIN_HEADLESS_ACCESS_AUTHORIZED || 'false' }}" in text
    assert "LINKEDIN_HEADLESS_PERMISSION_REFERENCE: ${{ secrets.LINKEDIN_HEADLESS_PERMISSION_REFERENCE }}" in text
    assert "LINKEDIN_POST_HEADLESS_QUERY: ${{ secrets.LINKEDIN_POST_HEADLESS_QUERY }}" in text
    assert "LINKEDIN_POST_SEARCH_INTENTS_PER_CYCLE: ${{ secrets.LINKEDIN_POST_SEARCH_INTENTS_PER_CYCLE || '6' }}" in text
    assert "LINKEDIN_POST_SCRAPER_SEARCH_PROVIDERS: ${{ secrets.LINKEDIN_POST_SCRAPER_SEARCH_PROVIDERS || 'bing_rss,duckduckgo,bing' }}" in text
    assert "SERPER_API_KEY: ${{ secrets.SERPER_API_KEY }}" in text
    assert "LINKEDIN_POST_SEARCH_QUERY: ${{ secrets.LINKEDIN_POST_SEARCH_QUERY ||" in text
    assert "LINKEDIN_POST_SCRAPER_QUERY: ${{ secrets.LINKEDIN_POST_SCRAPER_QUERY ||" in text
    assert "python -m playwright install --with-deps chromium" in text
    assert "APPLICATION_QUEUE_ENABLED: ${{ secrets.APPLICATION_QUEUE_ENABLED || 'false' }}" in text
    assert "APPLICATION_AUTO_SUBMIT: ${{ secrets.APPLICATION_AUTO_SUBMIT || 'false' }}" in text
    assert "APPLICATION_QUEUE_RESUME_FILE_ID: ${{ secrets.APPLICATION_QUEUE_RESUME_FILE_ID }}" in text
    assert "always() && env.APPLICATION_QUEUE_ENABLED == 'true'" in text
