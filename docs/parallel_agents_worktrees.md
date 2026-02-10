# Parallel Agent Workflow with Git Worktrees (Automated)

This workflow is mandatory for parallel agent execution.
Each agent creates its own branch/worktree and opens its own PR automatically.

## Prerequisites
- Base integration branch exists on remote: `marin`.
- GitHub remote is configured as `origin`.
- GitHub CLI is installed and authenticated:

```bash
gh auth status
```

If needed:

```bash
sudo apt install gh
gh auth login
```

## Python Dependencies (Per Worktree)
Each worktree has its own `backend/` folder. Use a per-worktree virtual environment to avoid missing deps:

```bash
scripts/bootstrap_venv.sh
source backend/.venv/bin/activate
```

## Automation Scripts
- Start worktree + branch:
  - `scripts/agent_worktree_start.sh --agent <agent-name> --task <task-id> --base marin`
- Push + open PR:
  - `scripts/agent_worktree_finish.sh --base marin --title "<PR title>" --body "<PR summary>"`

## Required Flow Per Agent Session
1. Start from the main repo checkout.
2. Create a dedicated worktree branch with `agent_worktree_start.sh`.
3. `cd` into the printed worktree path.
4. Implement scope and commit changes.
5. Run tests/validation relevant to the change.
6. Run `agent_worktree_finish.sh` to push and create PR.

No scoped work is allowed directly on `main` or `marin`.

## Example Commands by Agent

### Feature Agent (M1)
```bash
scripts/agent_worktree_start.sh --agent feature-agent --task M1 --base marin
cd .worktrees/marin-feature-agent-m1
# implement + commit
scripts/agent_worktree_finish.sh --base marin --title "feat: implement M1 engine/runtime" --body "Implements M1-T1..M1-T5 with tests and TASKS updates."
```

### Feature Agent (M2)
```bash
scripts/agent_worktree_start.sh --agent feature-agent --task M2 --base marin
cd .worktrees/marin-feature-agent-m2
# implement + commit
scripts/agent_worktree_finish.sh --base marin --title "feat: implement M2 API and UI" --body "Implements M2-T1..M2-T5 with tests and TASKS updates."
```

### Test Agent
```bash
scripts/agent_worktree_start.sh --agent test-agent --task M3-T1 --base marin
cd .worktrees/marin-test-agent-m3-t1
# implement + commit
scripts/agent_worktree_finish.sh --base marin --title "test: expand MVP regression coverage" --body "Implements M3-T1 coverage for engine/API failure paths."
```

### Review Agent
```bash
scripts/agent_worktree_start.sh --agent review-agent --task M1-M2-review --base marin
cd .worktrees/marin-review-agent-m1-m2-review
# add review artifacts/changes + commit
scripts/agent_worktree_finish.sh --base marin --title "review: M1/M2 risk findings" --body "Documents M1-T6 and M2-T6 findings with file references."
```

### Release Agent
```bash
scripts/agent_worktree_start.sh --agent release-agent --task M3-release --base marin
cd .worktrees/marin-release-agent-m3-release
# release checks + commit
scripts/agent_worktree_finish.sh --base marin --title "release: MVP readiness checks" --body "Executes M3-T4/M3-T5 checks and readiness report."
```

## Merge Integration
- Merge agent PRs into `marin`.
- After `marin` is stable, open PR from `marin` to `main`.

## Cleanup
After merged branches are no longer needed:

```bash
git worktree list
git worktree remove <worktree-path>
git branch -d <branch-name>
```
