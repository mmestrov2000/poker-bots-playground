# Parallel Agent Workflow with Git Worktrees

This runbook lets you run multiple Codex agent sessions at the same time without branch conflicts.

## 1) Repository and Branch Setup

Run from the main repo directory:

```bash
git status
```

### 1.1 Set the correct GitHub remote
If `origin` does not exist yet, add it:

```bash
git remote add origin <YOUR_GITHUB_REPO_URL>
```

If `origin` already exists but points to the wrong repository, replace it:

```bash
git remote set-url origin <YOUR_GITHUB_REPO_URL>
```

Example:

```bash
git remote set-url origin git@github.com:mmestrov2000/poker-bots-playground.git
```

### 1.2 Push bootstrap on `main`

```bash
git push -u origin main
```

### 1.3 Create and push development branch `marin`

```bash
git switch -c marin
git push -u origin marin
```

## 2) Worktree Layout

Create sibling worktree directories so each agent has its own branch and working copy:

```bash
mkdir -p ../worktrees
git worktree add ../worktrees/marin-feature-a -b marin-m1-engine marin
git worktree add ../worktrees/marin-feature-b -b marin-m2-ui marin
git worktree add ../worktrees/marin-test -b marin-tests marin
git worktree add ../worktrees/marin-review -b marin-review marin
git worktree add ../worktrees/marin-release -b marin-release marin
```

Recommended mapping:
- `marin-m1-engine`: `feature-agent` for M1 tasks.
- `marin-m2-ui`: `feature-agent` for M2 tasks.
- `marin-tests`: `test-agent` for M3-T1 and test hardening.
- `marin-review`: `review-agent` for milestone reviews.
- `marin-release`: `release-agent` for CI/release prep.

## 3) Agent Prompt Templates

Open each worktree in its own IDE window/session and start the matching agent.

### 3.1 Feature Agent Prompt (M1)

```text
[$feature-agent](skills/feature-agent/SKILL.md)
You are implementing Milestone 1 tasks from TASKS.md.

Scope:
- M1-T1, M1-T2, M1-T3, M1-T4, M1-T5

Requirements:
- Follow PROJECT_SPEC.md and ARCHITECTURE.md.
- Keep commits scoped and small.
- Update TASKS.md status for completed items.
- Add/extend backend tests.
- Summarize remaining gaps.
```

### 3.2 Feature Agent Prompt (M2)

```text
[$feature-agent](skills/feature-agent/SKILL.md)
You are implementing Milestone 2 tasks from TASKS.md.

Scope:
- M2-T1, M2-T2, M2-T3, M2-T4, M2-T5

Requirements:
- Follow PROJECT_SPEC.md and ARCHITECTURE.md.
- Keep API and UI behavior aligned with acceptance criteria.
- Update TASKS.md status for completed items.
- Add integration/UI smoke tests where applicable.
- Summarize follow-up items.
```

### 3.3 Test Agent Prompt

```text
[$test-agent](skills/test-agent/SKILL.md)
You are improving test coverage for poker-bots-playground MVP.

Scope:
- M3-T1 and any uncovered critical paths from M1/M2.

Requirements:
- Prioritize engine correctness, API failure cases, and regressions.
- Add tests for bot upload validation and match loop behavior.
- Update TASKS.md statuses relevant to testing work.
- Report uncovered risk areas.
```

### 3.4 Review Agent Prompt

```text
[$review-agent](skills/review-agent/SKILL.md)
Review the branch changes against PROJECT_SPEC.md, ARCHITECTURE.md, and TASKS.md.

Scope:
- M1-T6 and M2-T6 review responsibilities.

Requirements:
- Findings first: bugs, regressions, missing tests, security risks.
- Include file references for each issue.
- Distinguish must-fix from follow-up.
```

### 3.5 Release Agent Prompt

```text
[$release-agent](skills/release-agent/SKILL.md)
Validate release readiness for MVP.

Scope:
- M3-T4, M3-T5

Requirements:
- Run lint/test/CI-equivalent checks.
- Validate Docker compose run path and docs accuracy.
- Summarize readiness, residual risks, and go/no-go recommendation.
```

## 4) Merge Strategy

Use `marin` as integration branch for your work:

```bash
# Example from main repo checkout on branch marin
git switch marin
git pull

git merge --no-ff marin-m1-engine
git merge --no-ff marin-m2-ui
git merge --no-ff marin-tests
git merge --no-ff marin-review
git merge --no-ff marin-release

git push origin marin
```

After validation, create PR from `marin` to `main`.

## 5) Worktree Cleanup (after merge)

```bash
git worktree remove ../worktrees/marin-feature-a
git worktree remove ../worktrees/marin-feature-b
git worktree remove ../worktrees/marin-test
git worktree remove ../worktrees/marin-review
git worktree remove ../worktrees/marin-release
```
