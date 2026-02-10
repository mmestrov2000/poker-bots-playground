# Workflows

## Branching
- `main` is protected.
- Each developer works on a feature branch.
- PRs require at least one review.

## Task Updates
- Update TASKS.md when a task is started or completed.

## Agent Use
- Use one Codex session per agent role.
- Preferred: use skills from `skills/` so the role is preconfigured.
- Fallback: paste the prompt from `prompts/` at session start.

## Skill Installation
- Install skills from this repo into your Codex profile (one-time per machine).
- Use the skill installer to pull from your GitHub repo path.
- Restart Codex after installing skills so they appear in the UI.

## Parallel Agent Workflow
- For simultaneous multi-agent execution, use git worktrees.
- Agents must create branches/worktrees using `scripts/agent_worktree_start.sh`.
- Agents must push and create PRs using `scripts/agent_worktree_finish.sh`.
- Follow `docs/parallel_agents_worktrees.md` for end-to-end command flow.
