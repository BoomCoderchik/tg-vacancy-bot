# Application Queue

## Current Scope

The queue stores delayed Telegram application-button callbacks and private `/queue_resume` uploads for the operator. It does not currently include any source-specific automatic form-submission adapter.

When `APPLICATION_QUEUE_ENABLED=false`, `tg-vacancy-bot process-applications-once` exits without reading Telegram updates.

When enabled, the scheduled runner:

- reads pending Telegram callback and private message updates;
- accepts `/queue_resume` PDF/DOCX documents from the single allowlisted operator;
- stores only the Telegram `file_id` and safe original filename in SQLite;
- sends the operator a private "prepared" notification for a vacancy callback;
- attempts the browser-worker path only through registered adapters;
- reports the factual result in a private message.

Because no form adapter is currently registered, unsupported vacancy URLs are reported as not automatically submitted. The bot must not report `submitted` unless a future adapter proves a real success state.

## Required Configuration

- `TELEGRAM_BOT_TOKEN`
- `TARGET_CHAT_ID`
- exactly one `OPERATOR_USER_IDS` value
- `APPLICATION_QUEUE_ENABLED=true`
- `APPLICATION_AUTO_SUBMIT=true`
- `APPLICATION_QUEUE_PROFILE_FULL_NAME`
- `APPLICATION_QUEUE_PROFILE_EMAIL`

Optional queue fields:

- `APPLICATION_QUEUE_PROFILE_PHONE`
- `APPLICATION_QUEUE_PROFILE_PERSONAL_URL`
- `APPLICATION_QUEUE_PROFILE_COVER_LETTER`
- `APPLICATION_QUEUE_RESUME_FILE_ID`
- `APPLICATION_QUEUE_RESUME_FILE_NAME`

The preferred resume setup is to send a private PDF/DOCX document to the bot with the `/queue_resume` caption. The next queue run stores its Telegram file reference, so a resume `file_id` secret is not normally needed.

## Safety

Do not run `tg-vacancy-bot run` or `tg-vacancy-bot run-web` with `APPLICATION_QUEUE_ENABLED=true`; long polling and scheduled `getUpdates` must not consume the same bot token at the same time.

The queue never stores resume bytes in Git, logs, or the Actions cache. It downloads the selected resume into a temporary directory during a run and removes that directory when the run exits.
