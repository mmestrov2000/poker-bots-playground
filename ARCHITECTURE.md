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

## Batch 2 Architecture Extension
This section defines architectural additions for authentication, bot ownership, table lobby, leaderboard, and stronger runtime isolation.

## Extended Components
- `Auth Service`: local username/password login/logout/session handling and route protection.
- `User Store`: persistent user identity records.
- `Bot Registry Service`: per-user bot metadata and artifact lifecycle.
- `Table Lobby Service`: create/list/open table management.
- `Leaderboard Service`: persistent aggregate performance (`bb/hand`) per bot.
- `Bot Runtime Supervisor`: isolated bot execution boundary with strict resource/timeout limits.
- `Protocol Adapter`: builds normalized state payload for bot `act()` with full player/action context.

## Extended Runtime Flow
1. User logs in via `POST /api/v1/auth/login`; backend verifies username/password and issues authenticated session/token.
2. Authenticated user uploads bots via `POST /api/v1/my/bots`; metadata and artifacts are stored.
3. Lobby page calls `GET /api/v1/lobby/tables` and `GET /api/v1/lobby/leaderboard`.
4. User creates table via `POST /api/v1/lobby/tables` or opens an existing table.
5. At seat time, user either:
   - selects existing bot (`POST /tables/{table_id}/seats/{seat_id}/bot-select`), or
   - uploads inline and then selects.
6. Match loop calls Bot Runtime Supervisor, which:
   - executes bot in isolated boundary,
   - applies timeout and error guardrails,
   - returns normalized action or controlled fallback.
7. After each hand, table history and leaderboard aggregates are updated in persistent storage.

## Extended Repository Layout
- `backend/app/auth/` - auth routes, session utilities, auth middleware/dependencies.
- `backend/app/models/` - persistent models for users, bots, tables, leaderboard rows.
- `backend/app/services/bot_registry_service.py` - user bot management logic.
- `backend/app/services/lobby_service.py` - table create/list/open logic.
- `backend/app/services/leaderboard_service.py` - aggregate metrics and ranking.
- `backend/app/bots/supervisor.py` - isolated bot process/container execution orchestration.
- `backend/app/bots/protocol.py` - versioned bot-state payload builders.
- `frontend/login.html` - login route entrypoint (or SPA login route if existing app shell is adopted).
- `frontend/my-bots.*` - My Bots page script/style assets.
- `frontend/lobby.*` - Lobby list/create/leaderboard assets.

## Persistence Strategy (Batch 2)
- Move from memory+files-only to persistent storage for:
  - users
  - bot catalog metadata
  - table metadata
  - historical leaderboard aggregates
- Keep runtime hand history text file output for compatibility, while storing query metadata in DB.
- Default implementation target: SQLite for local/dev with migration path to Postgres.

## Extended State Model
### `User`
- `user_id`: string/uuid
- `username`: string
- `password_hash` or external provider subject id
- `created_at`: timestamp

### `BotRecord`
- `bot_id`: string/uuid
- `owner_user_id`: fk `User`
- `name`: string
- `version`: string
- `artifact_path`: filesystem/object store path
- `created_at`: timestamp

### `TableRecord`
- `table_id`: string/uuid
- `created_by_user_id`: fk `User`
- `small_blind`: numeric
- `big_blind`: numeric
- `status`: `waiting|running|finished`
- `created_at`: timestamp

### `LeaderboardRow`
- `bot_id`: fk `BotRecord`
- `hands_played`: integer
- `bb_won`: numeric
- `bb_per_hand`: numeric (derived or persisted cache)
- `updated_at`: timestamp

## Isolation and Security Hardening (Batch 2)
- Require isolated bot execution boundary (separate process minimum, container sandbox preferred).
- Enforce CPU/time/memory limits on bot decision calls.
- Deny bot access to platform-private services/storage and internal control-plane endpoints.
- Allow policy-controlled outbound connectivity so bots can use bot-managed services/databases when needed.
- Expose explicit protocol version field in bot context payload.
- Log per-bot runtime failures without impacting API availability.

## Protocol v2 Architecture Contract (M5-T1 Locked)
### Adapter Inputs and Outputs
- Input sources:
  - table/match metadata from `match_service`
  - per-street hand state from `engine.game`
  - per-action timeline from engine `ActionEvent` stream
- Output target:
  - versioned payload for `BotRunner.act(state)` where `state` is either legacy v1 or protocol v2.

### v2 Mapping Rules
- `table.hand_id`, `table.street`, blind values, and button seat map directly from engine round state.
- `hero` is derived from currently acting seat.
- `players` includes every active seat in seat-order, with stable `player_id` and current stack/bet/fold/all-in flags.
- `legal_actions` is normalized from engine legal-action computation, including min/max bounds when action uses amount.
- `action_history` is built from full hand action timeline in deterministic index order and includes `pot_after` snapshots.

### Compatibility Rules
- Version selection:
  - use `BOT_PROTOCOL_VERSION` module constant when present;
  - otherwise use `PokerBot.protocol_version` class attribute when present;
  - otherwise default to legacy v1 payload.
- Unsupported protocol declarations fail validation at upload time.
- Legacy v1 payload shape must remain unchanged while compatibility mode exists.

### Runtime Limits and Failure Policy
- Serialized state payload cap: `64KiB` (`65536` bytes).
- Per-decision timeout: default `2.0s`.
- If payload generation exceeds limits, bot times out, or bot returns invalid action schema:
  - record structured error,
  - substitute safe fallback action,
  - continue match loop without process crash.

## M4-T1 Policy Decisions
- Auth scope: username/password only in Batch 2 (no OAuth provider integration).
- Session model: server-side session with `HttpOnly` secure cookies.
- Visibility scope:
  - Bot source/artifacts/private metadata: owner-only.
  - Leaderboard metrics: public global ranking.
- Seating policy: same `bot_id` is allowed at multiple tables concurrently.
