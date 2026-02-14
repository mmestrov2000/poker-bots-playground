# Milestone 4 Review Report (M4-T8)

Date: 2026-02-14  
Branch: `marin-review-agent-m4-t8`

## Findings (by severity)

### High
- `backend/app/api/routes.py:265`, `backend/app/api/routes.py:302`, `backend/app/api/routes.py:311`, `backend/app/api/routes.py:320`, `backend/app/api/routes.py:329`, `backend/app/api/routes.py:338`
  - Legacy seat upload and match-control endpoints (`/seats/{seat_id}/bot`, `/match/start|pause|resume|end|reset`) are still unauthenticated, while M4 introduces authenticated ownership-based bot management.
  - Impact: Any unauthenticated caller can still upload arbitrary bot archives to active seats and control match lifecycle, bypassing the new auth boundary enforced on `/my/bots`, `/lobby/*`, and `/tables/{table_id}/seats/{seat_id}/bot-select`.
  - Regression/security risk: authorization model is inconsistent and can be bypassed through old write/control paths.
  - Required change: either (1) protect legacy write/control endpoints with `require_authenticated_user`, or (2) explicitly deprecate and disable them behind a compatibility flag with documented migration timeline.

### Medium
- `backend/app/api/routes.py:230`
  - `table_id` in `/tables/{table_id}/seats/{seat_id}/bot-select` is accepted but ignored; all requests mutate the singleton match state.
  - Impact: clients can send incorrect table ids without error, which can hide routing bugs and create future multi-table regressions.
  - Required change: validate supported `table_id` values (for current scope, reject non-`default`) and add a regression test.

## Test Gaps
- No integration/API test currently asserts that legacy write/control endpoints must be authenticated (or intentionally open and documented as an exception).
- No test asserts `table_id` validation semantics for `/tables/{table_id}/seats/{seat_id}/bot-select`.

## Validation Performed
- Commit/diff review across M4-T2..M4-T7 changes (`0b3064e` through `b6d9f4c`).
- Targeted tests:
  - `pytest backend/tests/test_api_endpoints.py backend/tests/test_frontend_auth_shell.py -q` (41 passed)
- Full backend regression:
  - `scripts/run_backend_pytest.sh` (62 passed)

## Final Risk Assessment
- Status: **NO-GO** for closing Milestone 4 security posture as complete until the high-severity auth bypass on legacy seat/match control paths is resolved or explicitly gated/deprecated.
- Residual risk after that fix: moderate (mainly future multi-table correctness around `table_id` handling).
