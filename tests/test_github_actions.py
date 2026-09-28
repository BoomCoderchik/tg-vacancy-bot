from pathlib import Path

import yaml


WORKFLOW = Path(".github/workflows/scheduled-source-polling.yml")
DIAGNOSTIC_WORKFLOW = Path(".github/workflows/diagnose-linkedin.yml")
OLD_WORKFLOW = Path(".github/workflows/poll-sources.yml")
README = Path("README.md")


def _load_workflow(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_scheduled_polling_workflow_is_valid_yaml() -> None:
    parsed = _load_workflow(WORKFLOW)

    assert parsed["name"] == "Scheduled vacancy source polling"
    env = parsed["jobs"]["poll"]["env"]
    # A glued YAML line would silently merge two env entries; make sure every
    # documented key survives parsing as its own entry.
    for key in (
        "ENABLE_LINKEDIN_POST_GUEST",
        "LINKEDIN_POST_APIFY_ACTOR",
        "SERPAPI_API_KEY",
        "ENABLE_LINKEDIN_POST_HEADLESS",
    ):
        assert key in env


def test_diagnostic_workflow_is_valid_yaml_and_dispatchable() -> None:
    parsed = _load_workflow(DIAGNOSTIC_WORKFLOW)

    # PyYAML parses an unquoted ``on:`` key as boolean True.
    triggers = parsed.get("on", parsed.get(True, {}))
    assert "workflow_dispatch" in triggers


def test_poll_sources_workflow_runs_every_15_minutes() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert not OLD_WORKFLOW.exists()
    assert 'cron: "7 * * * *"' in text
    assert 'cron: "22 * * * *"' in text
    assert 'cron: "37 * * * *"' in text
    assert 'cron: "52 * * * *"' in text
    assert "python -m tg_vacancy_bot.app --help" in text
    assert "python -m tg_vacancy_bot.app poll-once" in text
    assert "tg-vacancy-bot process-applications-once" not in text
    assert "SOURCE_POLL_INTERVAL_SECONDS: \"0\"" in text
    assert "concurrency:" in text


def test_poll_sources_workflow_preserves_dedupe_state() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "actions/cache@v5" in text
    assert "path: data/" in text
    assert "DATABASE_PATH: data/vacancies.sqlite3" in text
    assert "key: vacancy-db-${{ github.run_id }}" in text
    assert "vacancy-db-" in text


def test_package_readme_is_valid_utf8_for_pip_build() -> None:
    README.read_text(encoding="utf-8")


def test_poll_sources_workflow_defaults_optional_runtime_values() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "SOURCE_MAX_PUBLISH_PER_POLL: ${{ secrets.SOURCE_MAX_PUBLISH_PER_POLL || '20' }}" in text
    assert "SOURCE_MAX_AGE_HOURS: ${{ secrets.SOURCE_MAX_AGE_HOURS || '48' }}" in text
    # The single scheduled pipeline must follow /filters through repo variables.
    assert "VACANCY_FILTER_SPECIALTIES: ${{ vars.VACANCY_FILTER_SPECIALTIES }}" in text
    assert "VACANCY_FILTER_GRADES: ${{ vars.VACANCY_FILTER_GRADES }}" in text
    assert 'LOCALIZE_DESCRIPTIONS: "true"' in text
    assert "LOCALIZATION_PROVIDER: ${{ secrets.LOCALIZATION_PROVIDER || 'groq' }}" in text
    assert "GROQ_MODEL: ${{ secrets.GROQ_MODEL || 'openai/gpt-oss-120b' }}" in text
    assert "OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}" in text
    assert "GROQ_API_KEY: ${{ secrets.GROQ_API_KEY }}" in text
    assert "Verify required localization configuration" not in text
    assert "ENABLE_LINKEDIN_POST_HEADLESS: ${{ secrets.ENABLE_LINKEDIN_POST_HEADLESS || 'false' }}" in text
    assert "ENABLE_LINKEDIN_POST_SCRAPER: ${{ secrets.ENABLE_LINKEDIN_POST_SCRAPER || 'false' }}" in text
    assert "ENABLE_LINKEDIN_POST_APIFY: ${{ secrets.ENABLE_LINKEDIN_POST_APIFY || 'false' }}" in text
    assert "APIFY_API_TOKEN: ${{ secrets.APIFY_API_TOKEN }}" in text
    assert "LINKEDIN_HEADLESS_ACCESS_AUTHORIZED: ${{ secrets.LINKEDIN_HEADLESS_ACCESS_AUTHORIZED || 'false' }}" in text
    assert "LINKEDIN_HEADLESS_PERMISSION_REFERENCE: ${{ secrets.LINKEDIN_HEADLESS_PERMISSION_REFERENCE }}" in text
    assert "LINKEDIN_POST_HEADLESS_QUERY: ${{ secrets.LINKEDIN_POST_HEADLESS_QUERY }}" in text
    assert "LINKEDIN_POST_SEARCH_INTENTS_PER_CYCLE: ${{ secrets.LINKEDIN_POST_SEARCH_INTENTS_PER_CYCLE || '6' }}" in text
    assert "LINKEDIN_POST_SCRAPER_SEARCH_PROVIDERS: ${{ secrets.LINKEDIN_POST_SCRAPER_SEARCH_PROVIDERS || 'bing_rss,duckduckgo,bing,duckduckgo_lite,mojeek' }}" in text
    assert "SERPER_API_KEY:" not in text
    assert "LINKEDIN_POST_SEARCH_QUERY: ${{ secrets.LINKEDIN_POST_SEARCH_QUERY ||" in text
    assert "LINKEDIN_POST_SCRAPER_QUERY: ${{ secrets.LINKEDIN_POST_SCRAPER_QUERY ||" in text
    assert "python -m playwright install --with-deps chromium" in text
    assert "APPLICATION_AUTO_SUBMIT:" not in text
    assert "APPLICATION_QUEUE_RESUME_FILE_ID:" not in text
    assert "always() && env.APPLICATION_QUEUE_ENABLED == 'true'" not in text
    assert "ENABLE_HH_API: ${{ secrets.ENABLE_HH_API || 'false' }}" in text
    assert "HH_API_CONTACT_EMAIL: ${{ secrets.HH_API_CONTACT_EMAIL }}" in text
    assert "HH_API_QUERY: ${{ secrets.HH_API_QUERY }}" in text
    assert "HH_API_RESULTS_WANTED: ${{ secrets.HH_API_RESULTS_WANTED || '40' }}" in text
    assert "ENABLE_HABR_API: ${{ secrets.ENABLE_HABR_API || 'false' }}" in text
    assert "HABR_API_QUERY: ${{ secrets.HABR_API_QUERY }}" in text
    assert "HABR_API_RESULTS_WANTED: ${{ secrets.HABR_API_RESULTS_WANTED || '40' }}" in text
    assert "ENABLE_SUPERJOB_API: ${{ secrets.ENABLE_SUPERJOB_API || 'false' }}" in text
    assert "SUPERJOB_API_KEY: ${{ secrets.SUPERJOB_API_KEY }}" in text
    assert "SUPERJOB_API_QUERY: ${{ secrets.SUPERJOB_API_QUERY }}" in text
    assert "SUPERJOB_API_RESULTS_WANTED: ${{ secrets.SUPERJOB_API_RESULTS_WANTED || '40' }}" in text
    assert "ENABLE_TRUDVSEM_API: ${{ secrets.ENABLE_TRUDVSEM_API || 'false' }}" in text
    assert "TRUDVSEM_API_QUERY: ${{ secrets.TRUDVSEM_API_QUERY }}" in text
    assert "TRUDVSEM_API_RESULTS_WANTED: ${{ secrets.TRUDVSEM_API_RESULTS_WANTED || '40' }}" in text
    assert "ENABLE_ZP_API: ${{ secrets.ENABLE_ZP_API || 'false' }}" in text
    assert "ZP_API_QUERY: ${{ secrets.ZP_API_QUERY }}" in text
    assert "ZP_API_RESULTS_WANTED: ${{ secrets.ZP_API_RESULTS_WANTED || '40' }}" in text
