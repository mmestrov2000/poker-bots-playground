# Poker Bots Playground

Poker Bots Playground is a web platform for 2-6 player No-Limit Texas Hold'em bot battles. Users upload bots, seat them at a table, and run matches while the app tracks live hands, hand histories, P&L, and leaderboard results.

## Build a Bot

- Read the step-by-step guide: [docs/build-a-poker-bot.md](docs/build-a-poker-bot.md)
- If you want JavaScript, C++, Go, or another language: [docs/multi-language-bots.md](docs/multi-language-bots.md)
- Start from [bot/examples/python_bot/](bot/examples/python_bot/)
- Browse the other starter examples in [bot/examples/](bot/examples/)
- Use [bot/fixtures/sample_v2_state.json](bot/fixtures/sample_v2_state.json) to test locally

## Bot Contract
- Your upload is a `.zip` file.
- It must include a `bot.json` manifest and the files referenced by that manifest.
- On every decision, the server runs your declared command once.
- Your bot reads one state JSON object from `stdin`.
- Your bot writes one action JSON object to `stdout`.
- The transport is language-agnostic.
- The current runtime guarantees Python `3.12`, so the recommended event path is `["python", "bot.py"]`.
- Other languages work when their executable is available in the runtime. Examples and packaging notes are in [docs/multi-language-bots.md](docs/multi-language-bots.md).

Example `bot.json`:

```json
{
  "command": ["python", "bot.py"],
  "protocol_version": "2.0"
}
```

## Platform Features
- Authenticated `My Bots`, `Lobby`, and per-table pages.
- Six seats per table with start, pause, resume, end, and reset controls.
- Live hand simulation with readable hand-history detail.
- Persistent leaderboard metrics in `bb/hand`.
- Sandboxed bot execution with per-decision time, memory, and payload limits.

## Run Locally

### Docker Compose
```bash
docker compose up --build
```

Open `http://localhost:8000`.

Auth data is stored in `runtime/auth.sqlite3`. `docker-compose.yml` mounts `./runtime`, so users and uploads persist across restarts.

### Python Development
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
PYTHONPATH=. uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000`.
