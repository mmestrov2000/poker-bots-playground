# Architecture: Poker Bots Playground MVP

## Overview
The MVP uses a single Python backend service (`FastAPI`) and a static web frontend.
The backend manages bot uploads, match state, hand simulation, and hand history storage.
The frontend provides six bot upload slots plus live hand list and hand detail views.

## High-Level Components
- `Frontend (static HTML/CSS/JS)`: Upload bots, display seat status, show hands, open hand text.
- `API Layer (FastAPI routes)`: REST endpoints for upload, status, hand summaries, and hand detail.
- `Match Service`: Starts/stops match loop and coordinates hand simulation.
- `Poker Engine`: Handles Texas Hold'em hand progression and action resolution.
- `Bot Runner`: Loads user bot contract and executes `act` calls with timeout/error handling.
- `Hand Store`: Persists hand summaries and hand history text to runtime files.

## Runtime Flow
1. User uploads bot to Seat 1-6 (`POST /seats/{seat_id}/bot`).
2. API validates package shape and records seat occupancy.
3. When at least two seats are valid, Match Service sets match status to `running`.
4. Match loop repeatedly simulates hands:
   - Shuffle deck.
   - Execute preflop/flop/turn/river actions via Bot Runner.
   - Resolve winner/pot.
   - Generate summary + full hand history text.
   - Save hand record in memory and filesystem.
5. Frontend polls hand list and appends new rows.
6. User opens hand detail view from list item (`GET /hands/{hand_id}`).

## Repository Layout
- `backend/` - Python backend service.
- `backend/app/main.py` - FastAPI app factory and router mounting.
- `backend/app/api/routes.py` - HTTP endpoints.
- `backend/app/services/match_service.py` - in-memory match state + loop coordinator.
- `backend/app/engine/` - poker-domain logic and hand history formatting.
- `backend/app/bots/` - bot contract loading and execution wrappers.
- `backend/app/storage/` - runtime file persistence helpers.
- `backend/tests/` - backend test suite.
- `frontend/` - static UI assets.
- `frontend/index.html` - upload and hand list UI.
- `frontend/app.js` - API calls and UI state updates.
- `frontend/styles.css` - base UI styles.
- `bot_template/` - starter upload package reference.
- `bot_template/bot.py` - starter bot contract implementation.
- `bot_template/README.md` - packaging and upload instructions.
- `runtime/uploads/` - uploaded bot packages.
- `runtime/hands/` - generated hand history text files.
- `Dockerfile` - app container image.
- `docker-compose.yml` - local orchestration.

## State Model (MVP)
### `SeatState`
- `seat_id`: `1-6`
- `bot_name`: uploaded filename or bot identifier
- `ready`: bool
- `uploaded_at`: timestamp

### `MatchState`
- `status`: `waiting|running`
- `started_at`: timestamp
- `hands_played`: integer
- `last_hand_id`: string

### `HandRecord`
- `hand_id`: string
- `completed_at`: timestamp
- `summary`: string
- `winners`: list of seat ids
- `pot`: numeric
- `history_path`: filesystem path

## API Design
- Prefix: `/api/v1`
- Stateless HTTP API over JSON except hand history detail payload which includes raw text field.
- MVP data storage is memory + local files.
- `GET /leaderboard` returns per-seat BB/hand stats for the UI.
- Leaderboard stats are computed from per-hand deltas.

## Decisions
- Decision: `FastAPI` for backend.
- Rationale: Python-first stack, fast iteration, straightforward file upload and async support.

- Decision: Static frontend without bundler for MVP.
- Rationale: Minimal setup, easier bootstrap, adequate for two-upload and hand-list workflow.

- Decision: In-memory match state with runtime file storage.
- Rationale: Keeps MVP simple; allows future swap to DB/queue without changing user-facing behavior.

- Decision: Single-table-only MVP.
- Rationale: Matches product goal and reduces complexity before expanding to tournaments or lobbies.

## Security and Isolation
- Restrict upload size and accepted archive type.
- Validate expected bot entrypoint (`bot.py`, `PokerBot`).
- Execute bot actions behind timeout guards.
- Log bot exceptions and treat them as invalid actions.
- Future hardening path: container-per-bot sandbox with no network and resource limits.

## Observability
- Structured logs for:
  - upload attempts and validation failures
  - match state changes
  - hand completion summary
  - bot timeout/error events
- Health endpoint for liveness checks.

## Deployment Plan
- Build image with `Dockerfile`.
- Run with `docker-compose.yml` in development.
- Expose app on `8000` and persist `runtime/` via volume mount.
- VPS deployment can reuse the same image and environment variables.
