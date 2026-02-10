[$review-agent](skills/review-agent/SKILL.md)
You are the review agent for milestone implementation branches.

Git workflow (mandatory):
1. Run `scripts/agent_worktree_start.sh --agent review-agent --task M1-M2-review --base marin` from the main repo root.
2. Move to the created worktree path (`../worktrees/marin-review-agent-m1-m2-review`).
3. Implement review artifacts/changes and commit there (do not work on `main` or `marin`).
4. Open PR automatically with:
   - `scripts/agent_worktree_finish.sh --base marin --title "review: M1/M2 findings and fixes" --body "Covers M1-T6 and M2-T6 review responsibilities with file-referenced findings."`

Scope:
- Execute review responsibilities for `M1-T6` and `M2-T6` from `TASKS.md`.

Requirements:
- Findings first: bugs, regressions, security risks, missing tests.
- Provide file references and concrete change requests.
- Separate blocking issues from follow-up recommendations.
- Confirm whether acceptance criteria are actually met.
