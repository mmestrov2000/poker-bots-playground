# Project Spec: Poker Bots Playground MVP

## Summary
`poker-bots-playground` is a web application for 2-6 player No-Limit Texas Hold'em bot battles.
Users upload bots into Seats 1-6. Once at least two seats are filled, the backend starts simulating hands. The UI shows an append-only list of hand summaries and lets users open any hand as a readable poker hand history text.

## Target Users
- Poker bot developers who want quick short-handed testing.
- Engineers who want a simple environment to compare bot strategies.

## Goals
- Provide a web UI with six bot upload slots.
- Automatically start a battle when at least two slots are filled.
- Continuously simulate random hands and append them to a hand list.
- Provide detailed per-hand hand history text in a standard readable format.
- Run the app in containers for easy VPS deployment.

## Non-Goals (MVP)
- Authentication or user accounts.
- Tournament formats or multi-table support.
- Real-money integration.
- Advanced analytics, EV reports, or strategy dashboards.
- Long-term persistent storage beyond local runtime files.

## Scope
### In Scope
- Single active 2-6 player table.
- Texas Hold'em No Limit only.
- Bot upload via web UI to six fixed seats.
- Backend match loop that runs hands after at least two bots are uploaded.
- Hand summary list and detailed hand history viewer.
- Containerized local run and deployable image.

### Out of Scope
- Multi-match scheduling.
- Human manual play.
- Distributed workers.

## Core Assumptions
- Exactly one table exists in MVP.
- Default stack size is `100bb` per player.
- Default blinds are `0.5/1`.
- Cards are shuffled with secure random generation.
- Hands run continuously until a bot is replaced or match reset.
- Uploaded bots follow a predefined template contract.

## Functional Requirements
- `FR-01`: Web UI displays Seat 1-6 upload cards with current status.
- `FR-02`: Each seat accepts a bot package upload (`.zip`) and shows upload result.
- `FR-03`: Backend validates upload shape (required entrypoint file and class/function signature).
- `FR-04`: Match starts automatically when at least two seats contain valid bots.
- `FR-05`: Engine runs No-Limit Texas Hold'em hands for 2-6 players with random shuffles.
- `FR-06`: After each hand, backend stores:
  - hand id
  - timestamp
  - winner(s)
  - pot size
  - short summary line
  - full hand history text
- `FR-07`: UI appends each newly completed hand to the hand list without reloading.
- `FR-08`: User can click a hand list item to open full hand history text.
- `FR-09`: Backend exposes read endpoints for seat status, match status, hand list, hand detail, and leaderboard stats.
- `FR-10`: Bot decision calls have a timeout and invalid actions are handled safely.
- `FR-11`: User can reset the current match and clear in-memory state.
- `FR-12`: UI displays leaderboard sorted by BB/hand and allows toggling P&L lines per bot.

## Non-Functional Requirements
- `NFR-01` Correctness: Betting/action sequence must respect NLHE rules for 2-6 players.
- `NFR-02` Reliability: One bot crash/timeout must not crash the server process.
- `NFR-03` Performance: MVP target is at least 1 completed hand/second on a typical VPS.
- `NFR-04` Security: Uploaded files are size-limited and executed in constrained runtime.
- `NFR-05` Observability: Basic structured logs for uploads, hand completion, and bot errors.
- `NFR-06` Deployability: App must run through `docker compose` and a production Docker image.

## Bot Contract (MVP)
Bot package requirements:
- Upload a `.zip` file.
- Include `bot.py` at package root.
- Expose class `PokerBot` with method:

```python
class PokerBot:
    def act(self, state: dict) -> dict:
        """Return {'action': 'fold|check|call|bet|raise', 'amount': int} when needed."""
```

Runtime behavior:
- Each action call has a timeout (default `2s`).
- Invalid responses are treated as failed action and resolved safely by engine fallback.

## API Surface (MVP)
- `GET /api/v1/health`
- `GET /api/v1/seats`
- `POST /api/v1/seats/{seat_id}/bot` (seat_id 1-6)
- `GET /api/v1/match`
- `POST /api/v1/match/reset`
- `GET /api/v1/hands?page=1&page_size=100&max_hand_id=123`
- `GET /api/v1/pnl?since_hand_id=123` (per-seat deltas)
- `GET /api/v1/leaderboard`
- `GET /api/v1/hands/{hand_id}`

## Acceptance Criteria
- [ ] `AC-01` Opening the web app shows six upload slots and a hand list area.
- [ ] `AC-02` Uploading valid bot files to at least two seats starts the match automatically.
- [ ] `AC-03` Completed hands appear in the UI as appended summary rows.
- [ ] `AC-04` Clicking a hand opens readable `.txt`-style hand history content.
- [ ] `AC-05` Card dealing is random across consecutive hands.
- [ ] `AC-06` Bot timeout/invalid action is handled without taking down the app.
- [ ] `AC-07` App runs with `docker compose up --build`.
- [ ] `AC-08` Leaderboard shows BB/hand and toggles P&L lines per bot.

## Risks and Open Questions
- Running untrusted uploaded Python code is high risk; sandboxing must be treated as a first-class hardening task.
- Exact hand-history formatting convention (PokerStars-like vs custom readable standard) is to be finalized; MVP will use a consistent custom text format.
- Long-running in-memory state may require cleanup/rotation once hand volume grows.

## Test Strategy
### Unit Tests
- Deck generation and shuffle behavior.
- Action validation and fallback logic.
- Hand history text formatting.

### Integration Tests
- Upload flow: empty table -> one seat loaded -> both seats loaded -> match running.
- End-to-end hand pipeline in backend: simulate hand -> persist summary -> fetch detail.
- Match reset behavior.

### UI Tests
- Basic browser test: upload UI renders, hand list updates, hand detail modal/panel opens.

### Reliability Tests
- Bot timeout scenario.
- Bot throws runtime exception scenario.
- Invalid bot payload scenario.

## Batch 2 Expansion (Planned)
This section extends MVP scope for the next implementation batch. Existing MVP requirements remain valid unless explicitly superseded below.

## Expanded Goals
- Add authenticated user experience with a login page and persistent header/menu.
- Add `My Bots` page where users can upload, view, and manage personal bots.
- Let users select one of their uploaded bots when taking a seat, or upload directly from the seating flow.
- Move from single-table entry to a lobby page with table list and create-table flow.
- Add a persistent all-time leaderboard showing bot performance in `bb/hand`.
- Strengthen bot runtime isolation while improving server-to-bot state communication.

## Expanded Scope
### In Scope
- Login/logout flow for web users.
- Per-user bot catalog (`My Bots`) with bot metadata and artifact storage.
- Multi-table lobby and table detail pages.
- Table creation by users.
- Persistent leaderboard across all historical hands.
- Bot runtime protocol updates so bots can track other players and full hand action history.

### Out of Scope
- Social features (friends, chat, invites).
- Real-money wallets, rake, or payments.
- Cross-region distributed matchmaking.

## Functional Requirements (Batch 2)
- `FR-12`: App has a dedicated login page and authenticated app shell with header navigation.
- `FR-13`: Header includes links to Lobby, My Bots, and Logout.
- `FR-14`: Unauthenticated users are redirected to login for protected routes.
- `FR-15`: `My Bots` lists all bots owned by the current user with `bot_id`, name, version, status, and created timestamp.
- `FR-16`: User can upload a new bot from `My Bots` and receive clear validation feedback.
- `FR-17`: Seating flow supports selecting an existing owned bot or uploading a new bot inline.
- `FR-18`: Main page becomes Lobby and shows available tables with key status fields (table id, stakes/blinds, seats filled, state).
- `FR-19`: User can create a new table from Lobby.
- `FR-20`: Opening a table route shows the existing table experience (table view, PnL chart, hand summary/history).
- `FR-21`: System stores per-bot cumulative performance and exposes leaderboard sorted by `bb/hand`.
- `FR-22`: Leaderboard includes bots that have played historically, not only currently seated bots.
- `FR-23`: Bot runtime is isolated from API process (separate execution boundary and resource/time limits).
- `FR-24`: Server sends bots structured table context including player ids, seats, stacks, board, pot, legal actions, and complete prior hand actions.
- `FR-25`: Bot action interface remains backward compatible where possible, with explicit versioning for new context fields.
- `FR-26`: All new data (users, bots, tables, leaderboard aggregates) is persisted across process restarts.
- `FR-27`: Authentication for Batch 2 is local username/password only (no OAuth in this batch).
- `FR-28`: Bot source packages and implementation details are private to owners and never exposed in public APIs.
- `FR-29`: Leaderboard visibility is public and global across all historical tables/stakes.
- `FR-30`: A single bot can be seated at multiple tables concurrently.
- `FR-31`: Bot runtime may use bot-managed persistence/services (including external databases) while remaining isolated from platform internals.
- `FR-32`: Session model for web clients is server-side session with `HttpOnly` secure cookie authentication.

## API Surface (Batch 2 Additions)
- `POST /api/v1/auth/login`
- `POST /api/v1/auth/logout`
- `GET /api/v1/auth/me`
- `GET /api/v1/my/bots`
- `POST /api/v1/my/bots`
- `GET /api/v1/lobby/tables`
- `POST /api/v1/lobby/tables`
- `GET /api/v1/lobby/leaderboard`
- `POST /api/v1/tables/{table_id}/seats/{seat_id}/bot-select`

## Bot Protocol v2 Contract (M5-T1 Locked)
### Version Negotiation and Compatibility
- Bot interface remains `PokerBot.act(state: dict) -> dict`.
- Default protocol is legacy v1 when no explicit protocol declaration exists.
- Bot opts into v2 by declaring either:
  - module constant `BOT_PROTOCOL_VERSION = "2.0"`, or
  - class attribute `PokerBot.protocol_version = "2.0"`.
- Unsupported protocol values are rejected during upload validation with a clear error.
- Runtime always sends exactly one schema per call:
  - v1 bots receive the current legacy `state` shape unchanged.
  - v2 bots receive the v2 payload described below.

### Required v2 Payload Shape
All fields below are required unless explicitly marked optional.

- `protocol_version`: `"2.0"`
- `decision_id`: string, unique per bot decision request
- `table`: object
  - `table_id`: string
  - `hand_id`: string
  - `street`: `"preflop" | "flop" | "turn" | "river"`
  - `button_seat`: string
  - `small_blind`: int (chips, integer units)
  - `big_blind`: int (chips, integer units)
- `hero`: object
  - `player_id`: string
  - `seat_id`: string
  - `name`: string
  - `hole_cards`: list[string]
  - `stack`: int
  - `bet`: int
  - `to_call`: int
  - `min_raise_to`: int
  - `max_raise_to`: int
- `players`: list[object], ordered by seat position
  - `player_id`: string
  - `seat_id`: string
  - `name`: string
  - `stack`: int
  - `bet`: int
  - `folded`: bool
  - `all_in`: bool
  - `is_hero`: bool
- `board`: object
  - `cards`: list[string]
  - `pot`: int
- `legal_actions`: list[object]
  - `action`: `"fold" | "check" | "call" | "bet" | "raise"`
  - `min_amount`: int (optional for `fold`/`check`)
  - `max_amount`: int (optional for `fold`/`check`)
- `action_history`: list[object], full timeline within current hand
  - `index`: int (0-based sequence number)
  - `street`: `"preflop" | "flop" | "turn" | "river"`
  - `player_id`: string
  - `seat_id`: string
  - `action`: `"blind" | "fold" | "check" | "call" | "bet" | "raise"`
  - `amount`: int
  - `pot_after`: int
- `meta`: object
  - `server_time`: RFC3339 timestamp
  - `state_bytes`: int (serialized payload size in bytes)

### Constraint Contract
- Decision timeout: default `2.0s` per action call.
- State payload limit: serialized payload must be `<= 65536` bytes (`64KiB`).
- On timeout, oversized state, invalid response, or bot exception, engine applies safe fallback action and continues hand processing.

### Field Semantics
- All numeric chip values are integers in chip units (no floats).
- `player_id` must be stable for a seated bot across hands; `seat_id` may change between tables/hands.
- `action_history` is append-only, deterministic, and ordered by `index`.
- `legal_actions` is authoritative; bots must not assume unavailable actions are legal.

## Security Requirements (Batch 2 Auth)
- Passwords are never stored in plaintext; store salted adaptive hashes (`argon2id` preferred, `bcrypt` acceptable fallback).
- Login endpoint applies brute-force protections (rate limit and temporary lockout/backoff).
- Authenticated session/token must have expiration, logout invalidation, and secure transport-only handling.
- Protected endpoints must enforce authentication and ownership checks server-side (no client-trust assumptions).

## Acceptance Criteria (Batch 2)
- [ ] `AC-08` Unauthenticated access to Lobby/My Bots redirects to login.
- [ ] `AC-09` After successful login, header/menu is visible on protected pages.
- [ ] `AC-10` `My Bots` supports upload and displays bot cards with stable ids and metadata.
- [ ] `AC-11` Seating supports both selecting existing bot and direct upload.
- [ ] `AC-12` Lobby lists current tables and supports creating a new table.
- [ ] `AC-13` Opening a table from Lobby displays live table details, chart, and hand summary/history.
- [ ] `AC-14` Leaderboard returns historically active bots and persistent `bb/hand` values.
- [ ] `AC-15` Bot runtime failures or timeouts do not crash the server and are contained.
- [ ] `AC-16` Bot context payload includes enough information for tracking all opponents and actions.
- [ ] `AC-17` Username/password login enforces secure password storage and authenticated session checks.
- [ ] `AC-18` Bot code/artifacts are private; leaderboard entries remain publicly readable.
- [ ] `AC-19` The same `bot_id` can be seated at multiple tables without forced locking.
- [ ] `AC-20` Bot runtime can maintain bot-owned persistence without direct access to platform private data stores.

## M4-T1 Decisions (Locked)
- `D-01`: Auth method is local username/password only for Batch 2.
- `D-02`: Bot implementations/artifacts are private to owners; only performance data is public.
- `D-03`: One bot can be seated concurrently at multiple tables.
- `D-04`: Bots are runtime-isolated from platform internals and can use bot-managed persistence/services.
- `D-05`: Leaderboard scope is global ranking.
- `D-06`: Auth transport uses `HttpOnly` secure session cookies (server-managed session state).

## Test Strategy Additions (Batch 2)
### Backend Unit Tests
- Auth/session helpers and access-control guards.
- Bot catalog validation and metadata model.
- Leaderboard metric calculation (`bb/hand`) and persistence behavior.
- Bot context serializer for full player/action visibility.

### Backend Integration Tests
- Login -> protected endpoint access -> logout flow.
- My Bots upload/list flow with ownership enforcement.
- Lobby table create/list flow and table navigation payloads.
- Seat-by-selection flow using stored bot artifacts.
- Process restart persistence for users/bots/tables/leaderboard.

### UI Tests
- Route guards and login redirect behavior.
- Header navigation rendering for authenticated sessions.
- `My Bots` upload + list rendering.
- Lobby list/create interaction.
- Seat bot-select and inline-upload flows.

### Isolation/Safety Tests
- Bot timeout and crash containment in isolated runtime.
- Attempted access from bot process to platform-private services/data is denied.
- Bot runtime connectivity to bot-managed persistence endpoint works under policy.
- Malformed context handling in bot decision calls.
