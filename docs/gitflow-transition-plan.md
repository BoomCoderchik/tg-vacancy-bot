# GitFlow Transition Plan

Status: draft for owner approval.

## Goal

Update the project's Git and GitHub rules so Codex can work under a GitFlow-based process and, when the task requires it, push and merge verified changes into `main`.

This document is a proposal only. The binding rules in `AGENTS.md`, `docs/task-workflow.md`, and `docs/git-workflow.md` should be changed only after the owner approves this plan.

## Research Summary

Sources checked on 2026-07-13:

- [Atlassian Gitflow Workflow](https://www.atlassian.com/git/tutorials/comparing-workflows/gitflow-workflow)
- [Vincent Driessen's original Git branching model](https://nvie.com/posts/a-successful-git-branching-model/)
- [GitHub Flow documentation](https://docs.github.com/en/get-started/using-github/github-flow)
- [Pro Git: Basic Branching and Merging](https://git-scm.com/book/en/v2/Git-Branching-Basic-Branching-and-Merging)

Key findings:

- Classic GitFlow uses two long-lived branches: production-ready `main`/`master` and integration branch `develop`.
- Feature branches start from `develop` and merge back into `develop`.
- Release branches start from `develop`, are stabilized there, then merge into both `main` and `develop`.
- Hotfix branches start from `main` for urgent production fixes and merge back into both `main` and `develop`.
- Atlassian documents GitFlow as a legacy workflow that can be heavier than trunk-based or continuous-delivery workflows, but it still fits projects that need clearer release gates.
- GitHub's current flow emphasizes pull requests, checks, review, conflict handling, and branch protection before merging to the default branch. These practices should still be kept even when Codex is allowed to merge.

## Recommended Project Policy

Use an adapted GitFlow model:

- `main` is always production-ready.
- `develop` is the normal integration branch for completed work that is not yet released.
- `feature/<short-name>` branches are used for product features and non-urgent changes.
- `bugfix/<short-name>` branches are used for non-urgent fixes based on `develop`.
- `release/<version-or-date>` branches are used to prepare a production release from `develop`.
- `hotfix/<short-name>` branches are used for urgent fixes based on `main`.
- Existing Codex task branch names may keep the `codex/` prefix when useful, but their role should be explicit, for example `codex/feature/add-source-health-check` or `codex/hotfix/fix-telegram-publish`.

## Codex Permissions After Approval

After this plan is approved and the docs are updated, Codex is allowed to:

- create, update, and push GitFlow branches;
- merge verified `feature/*`, `bugfix/*`, and `codex/feature/*` branches into `develop`;
- create `release/*` branches from `develop`;
- merge verified `release/*` branches into `main` and back into `develop`;
- create `hotfix/*` branches from `main`;
- merge verified `hotfix/*` branches into `main` and back into `develop`;
- push `main` after a verified release or hotfix merge;
- push `develop` after syncing release or hotfix changes back.

Codex should still stop and report a blocker when:

- tests or required checks fail;
- GitHub remote access is missing or unauthorized;
- a branch protection rule blocks the merge;
- there are unrelated local changes that cannot be safely separated;
- the requested merge would include secrets, ignored runtime data, databases, logs, virtual environments, or unrelated user work;
- a production-impacting task requires missing service credentials, permissions, or deployment context.

## Merge Rules

### Feature and Bugfix Work

1. Start from latest `develop`.
2. Create a branch:
   - `feature/<short-name>` for features.
   - `bugfix/<short-name>` for non-urgent fixes.
   - `codex/feature/<short-name>` or `codex/bugfix/<short-name>` when Codex authors the branch.
3. Implement narrowly.
4. Run relevant checks.
5. Inspect the diff.
6. Commit and push the branch.
7. Merge into `develop` only after verification.
8. Push `develop`.

### Release Work

1. Start from latest `develop`.
2. Create `release/<version-or-date>`.
3. Allow only release stabilization changes:
   - bug fixes;
   - version, changelog, deployment, and documentation updates;
   - final configuration documentation.
4. Run the full relevant verification set.
5. Merge the release branch into `main`.
6. Tag the release when the project has a versioning convention.
7. Merge the same release branch back into `develop`.
8. Push `main`, `develop`, and tags.

### Hotfix Work

1. Start from latest `main`.
2. Create `hotfix/<short-name>` or `codex/hotfix/<short-name>`.
3. Fix only the urgent production issue.
4. Run the smallest sufficient check quickly, then broader checks when possible.
5. Merge into `main`.
6. Tag the hotfix when the project has a versioning convention.
7. Merge the hotfix back into `develop` or the active `release/*` branch.
8. Push `main`, `develop` or `release/*`, and tags.

## Pull Request Policy

Because the owner explicitly allows Codex to push and merge to `main`, pull requests should be optional rather than mandatory.

Recommended rule:

- Use direct merges for owner-approved Codex tasks, small documentation changes, release merges, and urgent hotfixes after local verification.
- Use pull requests when review history matters, when GitHub branch protection requires it, or when the owner asks for a PR.
- Do not bypass branch protection. If GitHub requires a PR, review, or status checks, Codex should follow that requirement or report the blocker.

## Verification Policy

Before any merge to `develop` or `main`, Codex must run checks that match the change:

- Documentation-only changes:
  - re-read changed files;
  - inspect `git diff`;
  - confirm links and instructions are coherent.
- Code changes:
  - run `.\.venv\Scripts\python.exe -m pytest`;
  - run any narrower tests relevant to the changed module when useful.
- Integration changes:
  - verify required environment variables and real-service boundaries;
  - do not add fake external-service behavior.
- GitHub Actions or deployment changes:
  - inspect workflow syntax;
  - run local checks where possible;
  - report any checks that require GitHub-side execution.

If verification cannot be run, Codex must say exactly why and must not merge into `main` unless the owner explicitly approves that risk.

## Documentation Changes To Make After Approval

1. Update `AGENTS.md`:
   - state that the project uses adapted GitFlow;
   - record the owner's authorization for Codex to push and merge verified changes into `main`;
   - keep the prohibition on unverified work, fake integrations, secrets, and unrelated changes.

2. Replace `docs/git-workflow.md` with the approved GitFlow policy:
   - branch model;
   - feature, bugfix, release, and hotfix flows;
   - direct merge versus PR rules;
   - required verification;
   - push and tag rules;
   - stop conditions.

3. Update `docs/task-workflow.md`:
   - point tasks to `develop` by default;
   - define when tasks may target `main` directly through hotfix or release flow;
   - require final sync back to `develop` after `main` hotfixes.

4. Optionally add a short note to `README.md`:
   - development uses GitFlow;
   - detailed rules live in `docs/git-workflow.md`.

## Acceptance Criteria For The Final Documentation Update

- [ ] Project docs define `main`, `develop`, `feature/*`, `bugfix/*`, `release/*`, and `hotfix/*`.
- [ ] Docs explicitly say Codex may push and merge verified changes to `main` when the approved workflow calls for it.
- [ ] Docs still require checks before merges.
- [ ] Docs still protect secrets, `.env`, databases, logs, caches, and unrelated user work.
- [ ] Docs explain when PRs are optional and when GitHub branch protection or owner request makes them required.
- [ ] Docs define hotfix back-merge into `develop`.
- [ ] Documentation-only verification is completed by re-reading changed files and inspecting the diff.

## Open Approval Question

Approve this adapted GitFlow policy as written, or specify changes to these points:

- Should Codex direct-merge to `main` after passing checks, or should it prefer PRs unless the task is urgent?
- Should release tags be required now, and if yes, what version format should be used?
- Should the default Codex branch naming stay `codex/<task>`, or switch fully to `feature/*`, `bugfix/*`, `release/*`, and `hotfix/*`?
