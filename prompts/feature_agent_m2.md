[$feature-agent](skills/feature-agent/SKILL.md)
You are the feature agent for Milestone 2 of poker-bots-playground.

Git workflow (mandatory):
1. Run `scripts/agent_worktree_start.sh --agent feature-agent --task M2 --base marin` from the main repo root.
2. Move to the created worktree path (`.worktrees/marin-feature-agent-m2`).
3. Implement and commit there (do not work on `main` or `marin`).
4. Open PR automatically with:
   - `scripts/agent_worktree_finish.sh --base marin --title "feat: implement M2 API and UI" --body "Implements M2-T1..M2-T5 with tests and TASKS updates."`

Scope:
- Implement `M2-T1`, `M2-T2`, `M2-T3`, `M2-T4`, `M2-T5` from `TASKS.md`.

Requirements:
- Follow `PROJECT_SPEC.md` and `ARCHITECTURE.md`.
- Keep API and frontend behavior aligned with acceptance criteria.
- Update task statuses in `TASKS.md` as items complete.
- Add integration/UI smoke tests where practical.
- Summarize completed scope and remaining follow-ups.
