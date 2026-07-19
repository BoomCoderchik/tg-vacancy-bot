# Multi-Agent Workflow

Use this guide when a task is large enough to behave like a real work session
rather than a single focused edit. The default remains one lead agent. Add
specialist AI agents only when parallel context gathering, independent design
work, implementation separation, or review pressure will materially improve the
result.

This project follows a manager-orchestrator pattern: the lead agent owns the
user conversation, final decisions, Git state, integration boundaries,
verification, and final report. Specialist agents may research, inspect, design,
implement bounded slices, or review, but the lead agent must reconcile their
outputs before changing shared behavior or reporting completion.

## When To Start Specialist Agents

Start specialist agents when at least two of these are true:

- The task spans several modules, for example bot behavior, source adapters,
  storage, Telegram callbacks, browser automation, docs, and tests.
- The work needs long-running research or broad codebase inspection that can be
  split into independent tracks.
- The solution has meaningful architecture, security, data, or real-integration
  risk.
- The task needs both implementation and independent review.
- The user request is explicitly a large session, roadmap item, migration,
  release, production incident, or multi-step feature.

Do not start specialist agents for routine documentation edits, obvious
one-file fixes, small parser tweaks, formatting changes, or questions that a
single agent can answer accurately after reading local context.

## Agent Limit

Use at most four specialist agents at the same time. Fewer is better. Start
with one or two specialists when the task has a clear bottleneck, and add more
only when their scopes are independent.

Recommended four-agent ceiling:

- Context Agent: maps docs, architecture, impacted files, prior tests, and
  constraints.
- Implementation Agent: works on one bounded code or documentation slice.
- Verification Agent: identifies and runs the most relevant checks, or prepares
  a verification plan when real services block execution.
- Review Agent: reviews diffs for regressions, security, integration safety,
  missing tests, and project-rule violations.

Use domain-specific names when clearer, such as Source Adapter Agent,
Telegram Flow Agent, Storage Agent, Browser Automation Agent, or Docs Agent.

## Collaboration Protocol

Before launching agents, the lead agent writes a compact session brief:

```text
Goal:
Context already read:
Constraints:
Done when:
Planned agents:
Shared files or areas:
Verification target:
Stop conditions:
```

Each specialist receives a bounded task with:

- Objective: one concrete outcome.
- Scope: files, modules, docs, commands, or flows to inspect or change.
- Non-goals: what the agent must not touch.
- Inputs: relevant docs, errors, commands, source links, or assumptions.
- Output contract: concise findings, changed files, tests run, blockers, and
  risks.

Agents must not edit the same file concurrently unless the lead agent explicitly
serializes the work. Prefer one writer per file or one writer plus one reviewer.
When two agents need the same file, the lead agent decides the final patch.

## Shared State

The lead agent maintains the task state in the current conversation. For large
sessions, keep an explicit checklist with at most one active item per agent.
Update it when agents finish, when assumptions change, or when verification
finds a problem.

Specialists should return distilled results, not raw transcripts. Useful
specialist output looks like:

```text
Summary:
Evidence:
Recommended change:
Files touched or inspected:
Checks run:
Blockers:
Residual risk:
```

The lead agent must merge duplicated findings, resolve conflicts, and label
inferences. If two agents disagree, inspect the underlying files or checks
directly before deciding.

## Execution Pattern

Use the simplest pattern that fits the task:

- Sequential: use when one step depends on another, such as schema analysis
  before implementation.
- Parallel: use when independent surfaces can be inspected at the same time,
  such as source adapter behavior, storage contracts, and docs.
- Evaluator-optimizer: use when quality criteria are explicit and a separate
  reviewer can materially improve the result, such as security-sensitive code,
  browser automation, or public documentation.

For this repository, a typical large feature flow is:

1. Lead agent reads required project docs and checks Git state.
2. Context Agent maps impacted architecture and tests.
3. One or two Implementation Agents work on independent slices, or one agent
   implements while another prepares tests.
4. Verification Agent runs focused checks and records blockers.
5. Review Agent inspects the final diff.
6. Lead agent reconciles outputs, runs any missing checks, commits, pushes, and
   reports.

## Project Safety Rules

All normal project rules still apply:

- Keep Telegram, source, OpenAI/Groq, LinkedIn, browser automation, and GitHub
  integrations real. Do not introduce fake fallbacks or placeholder vacancies.
- Do not print or commit secrets, `.env`, databases, logs, caches, or virtual
  environments.
- Preserve deduplication, vacancy filtering, operator allowlists, opt-in
  LinkedIn boundaries, and application confirmation boundaries.
- Stop instead of guessing when a real service, credential, permission, schema,
  or production resource is required but unavailable.
- The lead agent is responsible for final verification even when a specialist
  ran checks.

## Handoff Rules

Use handoffs only when a specialist should own a whole stage or conversation
segment. Use agents as tools when specialists should return bounded findings
to the lead agent and the lead should keep final control. For project work,
prefer the lead-controlled pattern unless the user explicitly asks to follow a
separate task or thread.

Every handoff must include enough context to avoid re-reading unrelated files,
but not so much that the specialist loses its focused role. Include exact files,
commands, branch, assumptions, and expected output.

## Sources Behind This Workflow

This workflow adapts these public multi-agent design principles:

- OpenAI Agents SDK recommends manager-style "agents as tools" when one agent
  should own synthesis and guardrails, and handoffs when a specialist should
  take over the active flow:
  https://openai.github.io/openai-agents-python/multi_agent/
- OpenAI Agents SDK describes handoffs as delegation to specialized agents:
  https://openai.github.io/openai-agents-python/handoffs/
- Anthropic recommends multi-agent systems when separate contexts,
  specialization, and parallel exploration create real value, especially under
  an orchestrator-subagent pattern:
  https://claude.com/blog/building-multi-agent-systems-when-and-how-to-use-them
- Anthropic's workflow guidance recommends starting simple, using parallelism
  for independent tasks, and using evaluator-optimizer loops only when quality
  criteria justify the extra cost:
  https://claude.com/blog/common-workflow-patterns-for-ai-agents-and-when-to-use-them
- Microsoft AutoGen emphasizes asynchronous multi-agent communication plus
  observability and debugging for complex agent systems:
  https://microsoft.github.io/autogen/stable/user-guide/core-user-guide/
