# Agent Roles and Usage

## Main Agent
Purpose: produce the initial project spec, architecture, and plan, and initialize the repo structure.

Responsibilities:
- Clarify requirements.
- Write `PROJECT_SPEC.md`, `ARCHITECTURE.md`, `TASKS.md`.
- Create initial folders/files.
- Summarize next steps.

## Feature Agent
Purpose: implement a scoped feature from `TASKS.md`.

Responsibilities:
- Implement the feature.
- Update `TASKS.md` status.
- Add/update tests.

## Review Agent
Purpose: review code changes for correctness, regressions, and missing tests.

Responsibilities:
- Identify bugs and risks.
- Request changes with clear rationale.
- Call out test gaps.

## Test Agent
Purpose: add or improve tests for a specific feature or area.

Responsibilities:
- Write tests based on spec and tasks.
- Focus on edge cases and regressions.

## Release Agent
Purpose: run full checks to validate readiness.

Responsibilities:
- Run test/lint/CI checks.
- Verify docs and versioning.
- Summarize readiness and risks.

## Mandatory Git Workflow (All Agents Except Main Bootstrap on `main`)
Every execution window for `feature-agent`, `test-agent`, `review-agent`, and `release-agent` must use a dedicated git worktree branch and open a PR automatically.

Required commands:
- Start worktree and branch:
  - `scripts/agent_worktree_start.sh --agent <agent-name> --task <task-id> --base marin`
- Finish and open PR:
  - `scripts/agent_worktree_finish.sh --base marin --title "<PR title>" --body "<PR summary>"`

Rules:
- Do not implement scoped feature work directly on `main` or `marin`.
- One worktree branch per agent scope (or per task when split finer).
- A branch is considered complete only after PR creation succeeds.
