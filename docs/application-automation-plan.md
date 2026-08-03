# Application Automation Plan

This document tracks the application-button and operator-profile foundation.

## Current Product State

- The bot stores one private operator profile behind `OPERATOR_USER_IDS`.
- The operator can upload or replace a PDF/DOCX resume through `/profile` or `/queue_resume`.
- Published normalized vacancy cards can include an application button.
- The application queue can process delayed Telegram callbacks in GitHub Actions.
- There are currently no source-specific automatic form-submission adapters.

## Safety Rules

- Do not report an application as `submitted` without a verified success state from a real supported integration.
- Do not add login flows, account cookies, proxies, CAPTCHA bypasses, fake identities, placeholder forms, mock submissions, or fake vacancy results.
- Do not store resume bytes in Git, logs, the public channel, or the Actions cache.
- Add a dedicated adapter only after the owner explicitly approves a real supported application path.

## Future Adapter Requirements

A future form adapter must:

- be explicitly allowlisted by domain;
- map only verified fields from the operator profile;
- stop on login, CAPTCHA, 2FA, changed markup, ambiguous forms, or unknown required fields;
- require focused tests for profile mapping, unsupported domains, missing profile data, browser safety stops, and success-state verification;
- update README, architecture, queue docs, environment examples, and GitHub Actions configuration.
