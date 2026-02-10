# New Project Instructions

This file describes exactly how to start a new project using the template repo and Codex skills.

## One-Time Setup (per developer machine)
1. Install the skills from the template repo:
   - Run:
     ```bash
     scripts/install_codex_skills.sh <owner>/<template-repo>
     ```
   - Example:
     ```bash
     scripts/install_codex_skills.sh acme/org-project-template
     ```
2. Restart Codex so the skills appear in the UI.

## Start a New Project (per project)
1. Create a new GitHub repository from this template.
2. Clone the new repo locally and open it in VS Code.
3. Start a new Codex session and select the `main-agent` skill.
4. Provide the project description and answer clarifying questions.
5. Let the main agent:
   - Fill `PROJECT_SPEC.md`
   - Fill `ARCHITECTURE.md`
   - Fill `TASKS.md`
   - Create any needed folders/files
6. Commit and push `main`.

## Developer Workflow (per feature)
1. Create a branch from `main`.
2. Open a new Codex session and select the `feature-agent` skill.
3. Implement the assigned task from `TASKS.md`.
4. Update `TASKS.md` status and add tests.
5. Open a new Codex session and select the `review-agent` skill to review changes.
6. Address review feedback.
7. Open a new Codex session and select the `test-agent` skill for additional test coverage if needed.
8. Open a new Codex session and select the `release-agent` skill before merging to `main`.

## Notes
- Always use one Codex session per agent role.
- If skills are unavailable, use prompt files in `prompts/` instead.
- Keep `PROJECT_SPEC.md`, `ARCHITECTURE.md`, and `TASKS.md` as the source of truth.
