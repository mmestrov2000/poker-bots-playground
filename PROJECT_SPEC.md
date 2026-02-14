# Project Spec: Poker Bots Playground MVP

## Summary
`poker-bots-playground` is a web application for heads-up (2-player) No-Limit Texas Hold'em bot battles.
Two users upload their bots into Seat A and Seat B. Once both seats are filled, the backend starts simulating hands. The UI shows an append-only list of hand summaries and lets users open any hand as a readable poker hand history text.

## Target Users
- Poker bot developers who want quick head-to-head testing.
- Engineers who want a simple environment to compare two bot strategies.

## Goals
- Provide a web UI with two bot upload slots.
- Automatically start a heads-up battle when both slots are filled.
- Continuously simulate random hands and append them to a hand list.
- Provide detailed per-hand hand history text in a standard readable format.
- Run the app in containers for easy VPS deployment.

## Non-Goals (MVP)
- Authentication, user accounts, or leaderboards.
- Tournament formats or multi-table support.
- Real-money integration.
- Advanced analytics, EV reports, or strategy dashboards.
- Long-term persistent storage beyond local runtime files.

## Scope
### In Scope
- Single active heads-up table.
- Texas Hold'em No Limit only.
- Bot upload via web UI to two fixed seats.
- Backend match loop that runs hands after both bots are uploaded.
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
- `FR-01`: Web UI displays Seat A and Seat B upload cards with current status.
- `FR-02`: Each seat accepts a bot package upload (`.zip`) and shows upload result.
- `FR-03`: Backend validates upload shape (required entrypoint file and class/function signature).
- `FR-04`: Match starts automatically when both seats contain valid bots.
- `FR-05`: Engine runs No-Limit Texas Hold'em heads-up hands with random shuffles.
- `FR-06`: After each hand, backend stores:
  - hand id
  - timestamp
  - winner
  - pot size
  - short summary line
  - full hand history text
- `FR-07`: UI appends each newly completed hand to the hand list without reloading.
- `FR-08`: User can click a hand list item to open full hand history text.
- `FR-09`: Backend exposes read endpoints for seat status, match status, hand list, and hand detail.
- `FR-10`: Bot decision calls have a timeout and invalid actions are handled safely.
- `FR-11`: User can reset the current match and clear in-memory state.

## Non-Functional Requirements
- `NFR-01` Correctness: Betting/action sequence must respect heads-up NLHE rules.
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
- `POST /api/v1/seats/{seat_id}/bot`
- `GET /api/v1/match`
- `POST /api/v1/match/reset`
- `GET /api/v1/hands?limit=50`
- `GET /api/v1/hands/{hand_id}`

## Acceptance Criteria
- [ ] `AC-01` Opening the web app shows two upload slots and a hand list area.
- [ ] `AC-02` Uploading valid bot files to both seats starts the match automatically.
- [ ] `AC-03` Completed hands appear in the UI as appended summary rows.
- [ ] `AC-04` Clicking a hand opens readable `.txt`-style hand history content.
- [ ] `AC-05` Card dealing is random across consecutive hands.
- [ ] `AC-06` Bot timeout/invalid action is handled without taking down the app.
- [ ] `AC-07` App runs with `docker compose up --build`.

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

## Open Questions for Clarification
- `Q-01`: Authentication method for this batch: local username/password only, or OAuth provider(s)?
- `Q-02`: Should bot visibility be private-only, or is shared/public bot visibility needed?
- `Q-03`: Can one bot sit at multiple tables concurrently, or should each deployment require a distinct instance/lock?
- `Q-04`: For "own database" support, is persistent per-bot writable storage required now, or can v1 isolate compute/runtime only?
- `Q-05`: Leaderboard scope: global across all stakes/tables, or filtered by blinds/table type?

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
- Attempted disallowed runtime access from bot process.
- Malformed context handling in bot decision calls.
