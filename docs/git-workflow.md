# GitFlow Workflow

This project uses GitHub with an adapted GitFlow process. Every completed
change needs a clear trail: scoped work, relevant verification, an intentional
commit, and a push to GitHub.

## Branch Model

- `main` — production-ready code only.
- `develop` — normal integration branch for completed work awaiting release.
- `feature/<short-name>` — new product work, created from `develop`.
- `bugfix/<short-name>` — non-urgent fixes, created from `develop`.
- `release/<version-or-date>` — release stabilization, created from `develop`.
- `hotfix/<short-name>` — urgent production fixes, created from `main`.

Use these role-based prefixes for every task branch. Do not use agent-specific
prefixes such as `codex/`; the branch name itself must show whether the work is
a feature, bugfix, release, or hotfix.

## Before Work

- Read the project instructions and check `git status --short --branch`.
- Confirm the `origin` GitHub remote is configured and reachable.
- Preserve unrelated worktree changes. Do not revert, overwrite, reformat, or
  commit them.
- Start normal work from the latest `develop`, not `main`.
- Do not put secrets, `.env` files, local databases, logs, caches, virtual
  environments, or intentionally ignored generated files into a commit.

## Feature And Bugfix Flow

1. Update `develop` from `origin/develop`.
2. Create `feature/<short-name>` or `bugfix/<short-name>` from `develop`.
3. Implement narrowly, run relevant checks, and inspect the diff.
4. Commit and push the branch.
5. Merge verified work into `develop`, then push `develop`.

## Release Flow

1. Create `release/<version-or-date>` from the latest `develop`.
2. Allow only stabilization: bug fixes, release/version notes, deployment, and
   configuration documentation.
3. Run the full relevant verification set and inspect the diff.
4. Merge the verified release into `main`; add a tag when a release version is
   defined.
5. Merge the same release back into `develop` and push both branches (and the
   tag, if created).

## Hotfix Flow

1. Create `hotfix/<short-name>` from the latest `main`.
2. Make only the urgent production fix and run the smallest sufficient checks,
   followed by broader checks when possible.
3. Merge verified work into `main`, then merge it back into `develop` (or an
   active release branch), and push every updated branch.

## Verification And Merges

- Code changes require relevant checks; at minimum run
  `./.venv/Scripts/python.exe -m pytest` when the project test environment is
  available.
- Documentation-only changes require re-reading the changed files and
  inspecting `git diff`.
- Validate real integration configuration and boundaries for integration work;
  never replace missing services with fake behavior.
- The owner authorizes Codex to create, push, and merge verified branches when
  this workflow calls for it. Pull requests are optional unless the owner asks
  for one or GitHub branch protection requires one.
- Never bypass branch protection, required reviews, or required checks. Report
  the blocker instead.

## Completion

Before reporting completion, inspect the final diff and confirm the commit is
scoped to the task. Report the branch, commit hash, push result, and any check
that could not run.
