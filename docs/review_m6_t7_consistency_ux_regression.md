# Milestone 6 Review Report (M6-T7)

Date: 2026-02-28  
Branch: `marin-review-agent-m6-t7`

## Findings (by severity)

### High
- `backend/app/api/routes.py:310`, `backend/app/api/routes.py:329`, `frontend/table-detail.js:388`
  - `table_id` is accepted in `POST /tables/{table_id}/seats/{seat_id}/bot-select` and sent by the UI, but server-side behavior ignores it and always mutates one global `match_service`.
  - Impact: selecting a bot from one table page changes shared seat state for every table route; table isolation promised by lobby/table UX is not enforced.
  - Required fix:
    - Validate `table_id` against a real table session/state object.
    - Route seat assignment to the specific table instance.
    - Return `404` for unknown table ids and `409/400` for invalid table-state transitions.

- `frontend/table-detail.js:565`, `frontend/table-detail.js:590`, `frontend/table-detail.js:595`, `frontend/table-detail.js:600`, `frontend/table-detail.js:605`, `frontend/table-detail.js:610`, `backend/app/api/routes.py:341`, `backend/app/api/routes.py:378`, `backend/app/api/routes.py:425`, `backend/app/api/routes.py:449`, `backend/app/api/routes.py:457`
  - Table detail reads and writes only global endpoints (`/seats`, `/match`, `/hands`, `/pnl`, `/leaderboard`) with no table scoping.
  - Impact: opening `/tables/<id>` does not provide table-specific gameplay state/history/leaderboard; controls operate on shared global runtime.
  - Required fix:
    - Introduce table-scoped API surface (`/tables/{table_id}/...`) for seats, match lifecycle, hands, pnl, and live leaderboard.
    - Update `table-detail.js` to call only table-scoped endpoints.
    - Add integration tests proving operations on table A do not affect table B.

- `backend/app/api/routes.py:341`, `backend/app/api/routes.py:346`, `backend/app/api/routes.py:378`, `backend/app/api/routes.py:383`, `backend/app/api/routes.py:392`, `backend/app/api/routes.py:401`, `backend/app/api/routes.py:410`, `backend/app/api/routes.py:420`
  - Legacy seat upload and match-control endpoints remain unauthenticated.
  - Impact: unauthenticated callers can inspect seat/match state and control match lifecycle regardless of lobby auth.
  - Required fix:
    - Protect legacy live-table endpoints with `require_authenticated_user` or remove/deprecate them behind an explicit compatibility flag.
    - Add regression tests for `401` on unauthenticated access to these endpoints.

### Medium
- `backend/app/api/routes.py:112`, `backend/app/api/routes.py:274`, `backend/app/auth/store.py:417`
  - Lobby table records are persistent, but response fields `seats_filled` and `status` are disconnected from actual gameplay state (`seats_filled` hardcoded to `0`, `status` never advanced).
  - Impact: lobby UX shows stale/inaccurate table state even while gameplay changes elsewhere.
  - Required fix:
    - Store and update per-table runtime status and ready-seat counts from table-scoped match state.
    - Return computed values in `GET /lobby/tables` and assert them in tests.

- `frontend/lobby.js:199`, `backend/app/api/routes.py:288`
  - Client-side validation allows `big_blind === small_blind`, while backend rejects `big_blind <= small_blind`.
  - Impact: avoidable 400 responses and inconsistent validation UX.
  - Required fix:
    - Align frontend validation to backend rule (`big_blind` must be strictly greater than `small_blind`).
    - Add a frontend smoke assertion for this constraint text/condition.

## Leaderboard Sorting Semantics Check
- Persistent leaderboard ordering is implemented in SQL as:
  - `bb_per_hand DESC`, then `hands_played DESC`, then `updated_at DESC`, then `bot_id DESC` (`backend/app/auth/store.py:490`).
- Current tests cover primary ordering and edge cases (`backend/tests/test_api_endpoints.py:715`, `backend/tests/test_api_endpoints.py:771`), but no tie-breaker-focused test exists.
- Required follow-up:
  - Add a deterministic test where `bb_per_hand` ties and verify secondary tie-breakers (`hands_played`, then `updated_at`, then `bot_id`).

## Validation Performed
- Diff and implementation review across M6-T1..M6-T6 artifacts (`backend/app/api/routes.py`, `backend/app/auth/store.py`, `backend/app/services/match_service.py`, `frontend/lobby.js`, `frontend/table-detail.js`, tests).
- Targeted tests:
  - `backend/.venv/bin/pytest backend/tests/test_api_endpoints.py backend/tests/test_frontend_auth_shell.py -q` (50 passed)

## Final Risk Assessment
- Status: **NO-GO** for marking Milestone 6 consistency/isolation as complete.
- Blocking reasons:
  - table route is not isolated by `table_id` in backend/runtime or frontend data fetching;
  - unauthenticated legacy control/read paths remain exposed.
