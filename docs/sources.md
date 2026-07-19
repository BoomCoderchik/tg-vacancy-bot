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

- XCrawl X Posts
  - Opt-in with `ENABLE_XCRAWL_X_POSTS=true`, `XCRAWL_API_KEY`, and a comma-separated `XCRAWL_X_HANDLES` list.
  - Uses XCrawl's documented `x_user_tweets` data API to read only the selected public X account timelines. It does not log in to X, create an account, or bypass access controls.
  - The API key remains in the local environment or GitHub Actions secrets; it is never committed. Each post has a stable `x.com/<handle>/status/<id>` URL for deduplication.
  - Posts pass through the same unified vacancy filtering and publication limits as every other source. The source reads the configured number of recent posts per account; dated posts are also subject to `SOURCE_MAX_AGE_HOURS`.

## Source policy

Automatic polling is deliberately limited to sources with a public feed and a documented no-registration path from the source site. When a source redirects to varied employer forms, it is manual-only until a dedicated and verified adapter exists for that specific form. Sites that require a job-seeker account on the source site, login, or browser scraping are not registered as sources. XCrawl X Posts is the explicit opt-in exception: it reads selected public account timelines through the operator's configured XCrawl API access and never uses an X account.

## Social-post exceptions

LinkedIn is retained as an explicit opt-in discovery source. It may use SerpApi, Serper, or public search results to discover post URLs. Search candidates are kept before vacancy and freshness filtering so the headless stage can inspect a real page rather than depend on a search snippet. Direct public-page headless reading additionally requires a documented LinkedIn permission or approved access path recorded through the fail-closed authorization settings. It never logs in to LinkedIn, creates an account, bypasses protection, or applies on the operator's behalf.

Every source vacancy is passed to the real description-localization provider before publication. If translation fails, the bot logs the error and publishes the original description with the vacancy link, so an operator can still inspect and open it. Russian source text is recognized and retained without an unnecessary model call.

## Planned source pattern

Add a new source only after verifying all of the following:

- The vacancy feed is a real public API or feed.
- A job seeker can use the supported application path without creating an account on the source site.
- Any source-level redirect to an employer form remains manual-only by default.
- A future application adapter is dedicated to one verified employer/ATS form and requires a final operator confirmation before submission.
- Tests cover registration, response mapping, and the application boundary.
