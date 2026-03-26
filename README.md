# Poker Bots Playground

Poker Bots Playground is a web platform for 2-6 player No-Limit Texas Hold'em bot battles. Users upload bots, seat them at a table, and run matches while the app tracks live hands, hand histories, P&L, and leaderboard results.

## Start Here

### If you are building a bot for the event
- Read the step-by-step guide: [docs/build-a-poker-bot.md](docs/build-a-poker-bot.md)
- Start from the starter package: [bot_template/](bot_template/)
- Browse readable example bots: [bot_template/examples/](bot_template/examples/)
- Use upload-ready sample archives: [bot_template/bots/](bot_template/bots/)

### Bot contract in one minute
- Your upload is a `.zip` file.
- It must include a `bot.json` manifest and the files referenced by that manifest.
- On every decision, the server runs your declared command once.
- Your bot reads one state JSON object from `stdin`.
- Your bot writes one action JSON object to `stdout`.
- The current runtime guarantees Python `3.12`, so the recommended event path is `["python", "bot.py"]`.

Example `bot.json`:

```json
{
  "command": ["python", "bot.py"],
  "protocol_version": "2.0"
}
```

## What the Platform Includes
- Authenticated `My Bots`, `Lobby`, and per-table pages.
- Six seats per table with start, pause, resume, end, and reset controls.
- Live hand simulation with readable hand-history detail.
- Persistent leaderboard metrics in `bb/hand`.
- Sandboxed bot execution with per-decision time, memory, and payload limits.

## Repository Guide
- [PROJECT_SPEC.md](PROJECT_SPEC.md): product requirements and bot protocol contract.
- [ARCHITECTURE.md](ARCHITECTURE.md): system design, runtime flow, and storage model.
- [TASKS.md](TASKS.md): milestone history and implementation checklist.
- [docs/parallel_agents_worktrees.md](docs/parallel_agents_worktrees.md): contributor workflow for multi-agent git worktrees.

## Run Locally

### Docker Compose
```bash
docker compose up --build
```

Open `http://localhost:8000`.

Auth data is stored in `runtime/auth.sqlite3`. `docker-compose.yml` mounts `./runtime`, so users and uploads persist across restarts.

### Python Development
```bash
scripts/bootstrap_venv.sh
source backend/.venv/bin/activate
PYTHONPATH=backend uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000`.

## Test the Repo

### Backend
```bash
scripts/run_backend_pytest.sh
```

### Frontend E2E
```bash
npm install
npm run install:e2e:browser
npm run test:e2e
```

Notes:
- Playwright starts `uvicorn` automatically.
- E2E runs use `.playwright-runtime/` so they do not reuse your normal `runtime/` data.

## Contributor Workflow
- Start a dedicated agent worktree: `scripts/agent_worktree_start.sh --agent <agent-name> --task <task-id> --base marin`
- Finish, push, and open the PR: `scripts/agent_worktree_finish.sh --base marin --title "<PR title>" --body "<PR summary>"`
- Full runbook: [docs/parallel_agents_worktrees.md](docs/parallel_agents_worktrees.md)
