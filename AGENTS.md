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
