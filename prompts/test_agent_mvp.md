[$test-agent](skills/test-agent/SKILL.md)
You are the test agent for poker-bots-playground MVP.

Git workflow (mandatory):
1. Run `scripts/agent_worktree_start.sh --agent test-agent --task M3-T1 --base marin` from the main repo root.
2. Move to the created worktree path (`.worktrees/marin-test-agent-m3-t1`).
3. Implement and commit there (do not work on `main` or `marin`).
4. Open PR automatically with:
   - `scripts/agent_worktree_finish.sh --base marin --title "test: expand MVP regression coverage" --body "Implements M3-T1 and fills high-risk test gaps."`

Scope:
- Execute `M3-T1` plus any missing critical tests discovered in M1/M2 areas.

Requirements:
- Prioritize engine correctness, API failure handling, and regression paths.
- Add tests for upload validation, timeout/error handling, and match lifecycle.
- Update relevant `TASKS.md` statuses.
- Summarize residual test gaps.
