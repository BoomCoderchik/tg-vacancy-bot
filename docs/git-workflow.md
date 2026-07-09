# Git Workflow

This project uses GitHub as the required remote repository. Every feature,
fix, documentation update, or other completed change must leave a clear git
trail: verified changes, logical commits, and a pushed task branch.

## Before Work

- Read the required project context from `AGENTS.md`.
- Check the current branch and worktree state:

  ```powershell
  git status --short --branch
  ```

- Confirm the GitHub remote is configured and reachable enough for normal git
  operations:

  ```powershell
  git remote -v
  ```

- Work on a feature branch named `codex/<short-task-name>` unless the current
  branch is already the correct task branch.
- Do not start implementation directly on `main` unless the user explicitly
  asks for that.

## Dirty Worktree Rules

- If there are uncommitted changes before starting, inspect them first.
- Preserve changes you did not make.
- Do not revert, delete, overwrite, reformat, or commit unrelated user changes.
- Continue only when the new task can be safely separated from existing
  changes. If it cannot be separated safely, report the blocker.

## During Work

- Keep each change scoped to the current task.
- Make logical commits after a complete and verified unit of work.
- Use concrete commit messages that describe what changed, for example:

  ```text
  Add git workflow instructions
  ```

- Do not commit secrets, `.env` contents, local databases, logs, virtual
  environments, caches, or generated artifacts that are intentionally ignored.

## Verification Before Commit

- Run checks that match the change.
- For code changes, run at least:

  ```powershell
  .\.venv\Scripts\python.exe -m pytest
  ```

- For documentation-only changes, re-read the changed docs and inspect the diff.
- If a required check cannot run, report why and what is needed to run it.
- Do not mark work as complete if verification failed or was skipped without a
  clear reason.

## End Of Task

- Inspect the final diff before committing:

  ```powershell
  git diff
  ```

- Commit the completed logical change.
- Push the task branch to GitHub after the task is done and verified:

  ```powershell
  git push -u origin <branch-name>
  ```

- Do not create a pull request automatically. Create a PR only when the user
  explicitly asks for one.
- In the final report, include the changed files, checks run, commit hash,
  branch name, and push result.

## Never Treat As Ready

- Unverified changes.
- Work with failing checks unless the failure is reported as a blocker.
- Placeholder integrations, fake Telegram publishing, fake source results, or
  invented vacancies.
- A local-only completed branch that has not been pushed, unless GitHub access
  or network permissions blocked the push and the blocker is reported.
