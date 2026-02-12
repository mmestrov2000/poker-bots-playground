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
