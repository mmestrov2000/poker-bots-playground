# Poker Bots Playground

Web playground for heads-up No-Limit Texas Hold'em bot battles.

## MVP Features
- Two bot upload seats (`A` and `B`) in a web UI.
- Automatic match start once both bots are uploaded.
- Continuous hand simulation with random outcomes.
- Append-only hand list with per-hand text history view.
- Containerized runtime for local development and VPS deployment.

## Project Docs
- `PROJECT_SPEC.md`
- `ARCHITECTURE.md`
- `TASKS.md`
- `docs/parallel_agents_worktrees.md`

## Local Run
### Option 1: Docker Compose
```bash
docker compose up --build
```

Open `http://localhost:8000`.

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
