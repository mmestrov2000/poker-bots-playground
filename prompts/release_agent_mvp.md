[$release-agent](skills/release-agent/SKILL.md)
You are the release agent for poker-bots-playground MVP.

Git workflow (mandatory):
1. Run `scripts/agent_worktree_start.sh --agent release-agent --task M3-release --base marin` from the main repo root.
2. Move to the created worktree path (`.worktrees/marin-release-agent-m3-release`).
3. Run `scripts/bootstrap_venv.sh` and `source backend/.venv/bin/activate` to install deps.
4. Implement release checks/docs updates and commit there (do not work on `main` or `marin`).
5. Open PR automatically with:
   - `scripts/agent_worktree_finish.sh --base marin --title "release: MVP readiness validation" --body "Executes M3-T4/M3-T5 checks and readiness report."`

Scope:
- Execute `M3-T4` and `M3-T5` from `TASKS.md`.

Requirements:
- Run and report lint/test/validation checks.
- Run backend tests via `scripts/run_backend_pytest.sh` for consistent environment and imports.
- Verify Docker and docs are consistent with actual behavior.
- Summarize release readiness, known risks, and go/no-go recommendation.
