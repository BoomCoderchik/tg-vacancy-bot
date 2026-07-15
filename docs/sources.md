# Sources

## Active source

- Arbeitnow API
  - Enabled with `ENABLE_ARBEITNOW=true`.
  - Uses the public `https://www.arbeitnow.com/api/job-board-api` endpoint; no source API key is required.
  - Each card links to an Arbeitnow vacancy, whose supported application form can be filled without an account after the operator has completed `/profile`.
  - The bot fills verified fields and attaches the local resume, but never submits an application automatically.
  - Publication date is parsed from `created_at` when present.

## Source policy

Automatic polling is deliberately limited to sources with a documented, no-registration application path. Sites that require a job-seeker account, paid/search APIs, login, browser scraping, or an unpredictable external application flow are not registered as sources.

## LinkedIn exception

LinkedIn is retained as an explicit opt-in discovery source. It may use SerpApi, Serper, public search-result scraping, or a public-page headless reader to find recent hiring posts. It never logs in to LinkedIn, creates an account, bypasses protection, or applies on the operator's behalf.

The source polling loop does not call a translation model. `LOCALIZE_DESCRIPTIONS` remains available only for explicit manual-message publishing flows.

## Planned source pattern

Add a new source only after verifying all of the following:

- The vacancy feed is a real public API or feed.
- A job seeker can use the supported application path without creating an account on the source site.
- The application form has a dedicated adapter and requires a final operator confirmation before submission.
- Tests cover registration, response mapping, and the application boundary.
