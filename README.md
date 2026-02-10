# Project Template

This repository is a reusable project starter for teams using Codex.

## What You Get
- Standard repo structure
- Canonical documents: spec, architecture, tasks
- Prompt templates for specialized agents
- Minimal workflows and scripts placeholders

## Quick Start (New Project)
1. Create a new repo from this GitHub template.
2. Open the repo locally in VS Code.
3. Start a main Codex session and run the `prompts/main_agent_bootstrap.md` prompt.
4. The main agent produces `PROJECT_SPEC.md`, `ARCHITECTURE.md`, and `TASKS.md` and initializes files.
5. Push `main` and let each developer branch from it.

## Repository Structure
- `PROJECT_SPEC.md` - canonical spec and acceptance criteria
- `ARCHITECTURE.md` - architecture and folder layout
- `TASKS.md` - task breakdown and ownership
- `AGENTS.md` - agent roles and usage
- `prompts/` - copy/paste prompts for each agent
- `docs/` - team docs and decisions
- `scripts/` - repo helper scripts
- `.github/workflows/` - CI skeleton

