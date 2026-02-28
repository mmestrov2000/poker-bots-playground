# Milestone 6 Batch-2 Release Readiness (M6-T8)

Date: 2026-02-28  
Branch: `marin-release-agent-m6-t8`

## Checks Run

| Check | Command | Result |
|---|---|---|
| Repository validation | `scripts/validate_repo.sh` | PASS |
| Environment bootstrap | `scripts/bootstrap_venv.sh` | PASS |
| Backend test suite | `scripts/run_backend_pytest.sh` | PASS (97 passed) |

## Docs and Environment Instruction Verification

### Command/runbook consistency
- Verified setup/test commands are consistent across:
  - `README.md`
  - `docs/workflows.md`
  - `docs/parallel_agents_worktrees.md`
- Confirmed documented validation commands exist and execute successfully in this worktree.

### Behavior-vs-doc consistency findings
- Batch-2 requirements and architecture imply multi-table/table-scoped behavior, but current runtime remains global for live gameplay APIs and state:
  - `table_id` is accepted but ignored in seat select handler: `backend/app/api/routes.py:310-338`.
  - Table detail page calls global live endpoints (`/seats`, `/match`, `/hands`, `/pnl`, `/leaderboard`) instead of table-scoped APIs:
    - `frontend/table-detail.js:280`
    - `frontend/table-detail.js:518`
    - `frontend/table-detail.js:526`
    - `frontend/table-detail.js:537`
    - `frontend/table-detail.js:566-568`
    - `frontend/table-detail.js:590`
    - `frontend/table-detail.js:595`
    - `frontend/table-detail.js:600`
    - `frontend/table-detail.js:605`
    - `frontend/table-detail.js:610`
- Legacy seat/match endpoints are still unauthenticated and callable without session guard:
  - `backend/app/api/routes.py:341-467`
- Lobby table metadata remains disconnected from live state (`seats_filled` hardcoded `0`):
  - `backend/app/api/routes.py:112-122`
- Frontend and backend blind validation rules are inconsistent:
  - frontend allows equality (`big_blind >= small_blind`): `frontend/lobby.js:199-201`
  - backend requires strict greater-than: `backend/app/api/routes.py:288-289`

## Blockers

1. Table isolation is not enforced for table routes (`table_id` ignored; global live runtime shared).
2. Unauthenticated access remains possible for legacy live seat/match read-write endpoints.

## Residual Risks (Non-Blocking but Important)

1. Lobby shows stale/inaccurate `seats_filled` and status values.
2. Client/server validation mismatch for blind configuration causes avoidable 400 responses.
3. Leaderboard tie-breaker ordering semantics still lack a dedicated deterministic regression test.

## Recommendation

- Go/No-Go for M6 Batch-2 release readiness: **NO-GO**.
- Reason: high-severity consistency/security blockers above remain unresolved in current branch state despite green backend tests.
