# Poker Bots Playground

Web playground for 2-6 player No-Limit Texas Hold'em bot battles.

## MVP Features
- Six bot upload seats (`1`-`6`) in a web UI.
- Match controls for start/pause/resume/end once at least two bots are seated.
- Continuous hand simulation with random outcomes.
- Append-only hand list with per-hand text history view.
- Leaderboard sorted by BB/hand with P&L line toggles.
- Containerized runtime for local development and VPS deployment.

## Project Docs
- `PROJECT_SPEC.md`
- `ARCHITECTURE.md`
- `TASKS.md`
- `docs/parallel_agents_worktrees.md`

## Agent Prompt Presets
- `prompts/feature_agent_m1.md`
- `prompts/feature_agent_m2.md`
- `prompts/test_agent_mvp.md`
- `prompts/review_agent_milestones.md`
- `prompts/release_agent_mvp.md`

## Automated Agent Git Flow
- Start worktree/branch: `scripts/agent_worktree_start.sh --agent <agent-name> --task <task-id> --base marin`
- Push and create PR: `scripts/agent_worktree_finish.sh --base marin --title "<PR title>" --body "<PR summary>"`
- Detailed runbook: `docs/parallel_agents_worktrees.md`

## Python Setup (Per Worktree)
```bash
scripts/bootstrap_venv.sh
source backend/.venv/bin/activate
```

## Backend Tests (Per Worktree)
```bash
scripts/run_backend_pytest.sh
```

## Local Run
### Option 1: Docker Compose
```bash
docker compose up --build
```

Open `http://localhost:8000`.

### Asset Versioning (Production)
Set `APP_ASSET_VERSION` per deployment (for example to a git SHA or release tag) so browsers load new JS/CSS after deploy:

```bash
APP_ASSET_VERSION=$(git rev-parse --short HEAD) docker compose up --build -d
```

### Option 2: Python (backend + static frontend)
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
PYTHONPATH=. uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000`.

## Bot Upload Contract
Upload `.zip` with `bot.py` at root and class `PokerBot`.
See `bot_template/README.md`.

## Current State
This repo contains MVP bootstrap scaffolding. Core NLHE rules and robust bot sandboxing are tracked in `TASKS.md`.
