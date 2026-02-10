[$feature-agent](skills/feature-agent/SKILL.md)
You are the feature agent for Milestone 1 of poker-bots-playground.

Git workflow (mandatory):
1. Run `scripts/agent_worktree_start.sh --agent feature-agent --task M1 --base marin` from the main repo root.
2. Move to the created worktree path (`.worktrees/marin-feature-agent-m1`).
3. Run `scripts/bootstrap_venv.sh` and `source backend/.venv/bin/activate` to install deps.
4. Implement and commit there (do not work on `main` or `marin`).
5. Open PR automatically with:
   - `scripts/agent_worktree_finish.sh --base marin --title "feat: implement M1 engine/runtime" --body "Implements M1-T1..M1-T5 with tests and TASKS updates."`

Scope:
- Implement `M1-T1`, `M1-T2`, `M1-T3`, `M1-T4`, `M1-T5` from `TASKS.md`.

Requirements:
- Follow `PROJECT_SPEC.md` and `ARCHITECTURE.md`.
- Keep changes scoped to Milestone 1.
- Update task statuses in `TASKS.md` as items complete.
- Add/adjust backend tests for engine and bot runtime behavior.
- Summarize completed scope and remaining risks.
