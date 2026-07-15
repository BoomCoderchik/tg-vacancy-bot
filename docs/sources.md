# Sources

## Active sources

- Arbeitnow API
  - Enabled with `ENABLE_ARBEITNOW=true`.
  - Uses the public `https://www.arbeitnow.com/api/job-board-api` endpoint; no source API key is required.
  - Each card links to an Arbeitnow vacancy, whose supported application form can be filled without an account after the operator has completed `/profile`.
  - The bot fills verified fields and attaches the local resume, but never submits an application automatically.
  - Publication date is parsed from `created_at` when present.

- Working Nomads API
  - Enabled with `ENABLE_WORKING_NOMADS=true`.
  - Uses the public `https://www.workingnomads.com/api/exposed_jobs/` JSON feed; no source API key or Working Nomads account is required.
  - Each vacancy URL is a Working Nomads redirect to the employer's actual application path. The bot records the operator's request and provides that link for a manual application.
  - It has no generic browser form adapter: employer/ATS forms differ, so no credentials are used and no fields are auto-filled or submitted from this source.
  - Publication date is parsed from `pub_date` when present.

## Source policy

Automatic polling is deliberately limited to sources with a public feed and a documented no-registration path from the source site. When a source redirects to varied employer forms, it is manual-only until a dedicated and verified adapter exists for that specific form. Sites that require a job-seeker account on the source site, paid/source APIs, login, or browser scraping are not registered as sources.

## LinkedIn exception

LinkedIn is retained as an explicit opt-in discovery source. It may use SerpApi, Serper, public search-result scraping, or a public-page headless reader to find recent hiring posts. It never logs in to LinkedIn, creates an account, bypasses protection, or applies on the operator's behalf.

Every source vacancy is passed to the real description-localization provider before publication. If translation fails, the bot logs the error and publishes the original description with the vacancy link, so an operator can still inspect and open it. Russian source text is recognized and retained without an unnecessary model call.

## Planned source pattern

Add a new source only after verifying all of the following:

- The vacancy feed is a real public API or feed.
- A job seeker can use the supported application path without creating an account on the source site.
- Any source-level redirect to an employer form remains manual-only by default.
- A future application adapter is dedicated to one verified employer/ATS form and requires a final operator confirmation before submission.
- Tests cover registration, response mapping, and the application boundary.
