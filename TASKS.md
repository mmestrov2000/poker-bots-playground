# Tasks

## Status Legend
- `[ ]` Todo
- `[~]` In Progress
- `[x]` Done

## Owner Legend
- `main-agent`: project bootstrap and documentation ownership
- `feature-agent`: implementation ownership (backend/frontend features)
- `test-agent`: dedicated test coverage and regression ownership
- `review-agent`: code review and risk assessment ownership
- `release-agent`: CI, release readiness, and final validation ownership

## Milestone 0: Project Bootstrap
Goal: lock MVP scope and create initial runnable scaffold.

- [x] `M0-T1` Finalize product requirements in `PROJECT_SPEC.md` (owner: `main-agent`)
  - Acceptance: Goals, scope, requirements, acceptance criteria, and test strategy are concrete and MVP-focused.
  - Test Strategy: Manual doc review against clarified answers.
- [x] `M0-T2` Define technical architecture in `ARCHITECTURE.md` (owner: `main-agent`)
  - Acceptance: Components, data flow, repo layout, security, and deployment baseline are specified.
  - Test Strategy: Cross-check architecture paths against created files/folders.
- [x] `M0-T3` Create milestone-based execution plan in `TASKS.md` (owner: `main-agent`)
  - Acceptance: Tasks are small, unambiguous, and assigned.
  - Test Strategy: Verify each task has owner, status, and acceptance intent.
- [x] `M0-T4` Scaffold backend/frontend/container starter structure (owner: `main-agent`)
  - Acceptance: Repo contains backend app entrypoint, frontend placeholder UI, bot template, Docker files, runtime dirs.
  - Test Strategy: Syntax check for Python files and file presence check.

## Milestone 1: Game Engine and Bot Runtime
Goal: run valid heads-up NLHE hands between uploaded bots.

- [x] `M1-T1` Implement core heads-up NLHE hand state model (owner: `feature-agent`)
  - Acceptance: Engine tracks blinds, stacks, betting rounds, pot, board, and showdown state.
  - Test Strategy: Unit tests for transitions across preflop/flop/turn/river.
- [x] `M1-T2` Implement legal action validation and bet sizing rules (owner: `feature-agent`)
  - Acceptance: Illegal actions are rejected or normalized by explicit fallback rules.
  - Test Strategy: Unit tests for fold/check/call/bet/raise edge cases.
- [x] `M1-T3` Implement secure bot loader and `act()` invocation wrapper (owner: `feature-agent`)
  - Acceptance: Bot class is loaded from upload package; timeout/error handling is enforced.
  - Test Strategy: Unit tests for valid bot, timeout bot, exception bot, malformed bot.
- [x] `M1-T4` Integrate match loop to produce completed hand records (owner: `feature-agent`)
  - Acceptance: With two bots loaded, loop generates sequential hand ids and results.
  - Test Strategy: Integration test for match start and first N completed hands.
- [x] `M1-T5` Generate readable `.txt` hand history formatter (owner: `feature-agent`)
  - Acceptance: Each completed hand has standard, human-readable text output.
  - Test Strategy: Snapshot tests for representative hand histories.
- [x] `M1-T6` Review M1 implementation changes and request fixes (owner: `review-agent`)
  - Acceptance: Critical bugs/risks are documented with file references and required fixes.
  - Test Strategy: Review checklist + targeted rerun of affected tests.

## Milestone 2: API and Web UX
Goal: provide end-user upload and hand browsing experience.

- [x] `M2-T1` Implement seat upload and validation endpoints (owner: `feature-agent`)
  - Acceptance: `POST /api/v1/seats/{seat_id}/bot` stores upload, validates shape, updates seat readiness.
  - Test Strategy: API integration tests for valid and invalid uploads.
- [x] `M2-T2` Implement match status and reset endpoints (owner: `feature-agent`)
  - Acceptance: UI can read running state and reset match state safely.
  - Test Strategy: API integration tests for waiting -> running -> reset flow.
- [x] `M2-T3` Implement hands list and hand detail endpoints (owner: `feature-agent`)
  - Acceptance: API returns summaries and per-hand full text by id.
  - Test Strategy: Integration tests for pagination and hand lookup behavior.
- [x] `M2-T4` Build frontend upload controls and seat status panels (owner: `feature-agent`)
  - Acceptance: Users can upload bots into both seats and see status updates.
  - Test Strategy: Browser smoke test for upload flow.
- [x] `M2-T5` Build live hand list and hand detail view (owner: `feature-agent`)
  - Acceptance: New hands appear in order and detail text opens on click.
  - Test Strategy: Browser smoke test for list polling and detail rendering.
- [x] `M2-T6` Review M2 API/UI changes and call out regressions (owner: `review-agent`)
  - Acceptance: Review feedback is documented and blocking issues are resolved before merge.
  - Test Strategy: Manual API/UI verification against acceptance criteria.

## Milestone 3: Quality, Hardening, and Release
Goal: make MVP stable and deploy-ready.

- [x] `M3-T1` Add comprehensive backend test suite for engine and API (owner: `test-agent`)
  - Acceptance: Critical flows and failure paths are covered.
  - Test Strategy: `pytest` suite green locally and in CI.
- [x] `M3-T2` Add bot upload constraints and runtime safeguards (owner: `feature-agent`)
  - Acceptance: Upload size limits, extension checks, and execution guardrails are enforced.
  - Test Strategy: Negative tests for oversized and malformed uploads.
- [x] `M3-T3` Finalize Docker image and compose workflow (owner: `feature-agent`)
  - Acceptance: `docker compose up --build` boots app with persisted `runtime/` volume.
  - Test Strategy: Manual compose run and health endpoint check.
- [x] `M3-T4` Expand CI workflow for lint/test checks (owner: `release-agent`)
  - Acceptance: CI runs repository validation plus backend tests.
  - Test Strategy: Open PR and confirm CI success.
- [x] `M3-T5` Perform release readiness review (owner: `release-agent`)
  - Acceptance: Known risks, test results, and deployment notes are documented.
  - Test Strategy: Release checklist review in PR.

## Bugfix: Hand Detail Selection
Goal: keep Hand Detail stable until a user selects a different hand.

- [x] `BF-T1` Stop auto-updating Hand Detail on polling; only update on user selection (owner: `feature-agent`)
  - Acceptance: Hand Detail stays on the selected hand while new hands are played; initial state stays empty prompt.
  - Test Strategy: Manual UI check during live polling.
- [x] `BF-T2` Clear Hand Detail on match reset or bot re-upload (owner: `feature-agent`)
  - Acceptance: Reset/re-upload returns Hand Detail to the empty prompt and clears selection.
  - Test Strategy: Manual UI check after reset and re-upload.

## Feature: Modern Table UI + Match Controls
Goal: add a poker table layout with seat taking and match control buttons.

- [x] `F4-T1` Create a new branch from main for feature work (owner: `feature-agent`)
- [x] `F4-T2` Extend match service state to support start/pause/resume/end without auto-start on upload (owner: `feature-agent`)
- [x] `F4-T3` Add match control API endpoints for start/pause/resume/end (owner: `feature-agent`)
- [x] `F4-T4` Redesign frontend layout with a modern table and seat controls (owner: `feature-agent`)
- [x] `F4-T5` Wire frontend seat uploads and match control buttons to new endpoints (owner: `feature-agent`)
- [x] `F4-T6` Add/update backend tests for match control flows (owner: `test-agent`)
- [ ] `F4-T7` Run manual UI smoke test for seating and match controls (owner: `feature-agent`)

## Feature: Hand History On-Demand Pagination
Goal: gate hand history behind a button with snapshot-based pagination and page-size controls.

- [x] `FHH-T1` Add paginated `/hands` API with snapshot boundary (owner: `feature-agent`)
  - Acceptance: `/hands` supports `page`, `page_size` (100/250/1000), and `max_hand_id`; returns stable slices plus metadata.
  - Test Strategy: Update/add coverage in `test_match_service.py` and `test_api_endpoints.py`.
- [x] `FHH-T2` Update frontend to hide hand history until button press and add pagination controls (owner: `feature-agent`)
  - Acceptance: Hand History button reveals snapshot list; page size menu and prev/next navigation work; hand detail remains unchanged.
  - Test Strategy: Manual UI smoke test during running match.
- [x] `FHH-T3` Update API documentation for new `/hands` parameters (owner: `main-agent`)
  - Acceptance: `PROJECT_SPEC.md` reflects the new query parameters and defaults.
  - Test Strategy: Doc review.
- [~] `FHH-T4` Validate and open PR after tests pass (owner: `release-agent`)
  - Acceptance: `scripts/run_backend_pytest.sh` passes and PR is opened after local validation.
  - Test Strategy: Attach test output or CI status to PR.

## Feature: P&L Graph + Arena Layout
Goal: add a real-time P&L chart alongside the poker table.

- [x] `FPNL-T1` Add P&L API endpoint and match service helper (owner: `feature-agent`)
  - Acceptance: `/api/v1/pnl` returns per-hand P&L deltas and last hand id.
  - Test Strategy: Unit/API tests for P&L responses and snapshot behavior.
- [x] `FPNL-T2` Update frontend layout with right-side P&L chart (owner: `feature-agent`)
  - Acceptance: Table shifts left, graph shows two curves, legend updates with color-coded net P&L.
  - Test Strategy: Manual UI smoke test with running match.
- [x] `FPNL-T3` Update documentation and validations (owner: `feature-agent`)
  - Acceptance: PROJECT_SPEC API surface lists /pnl endpoint.
  - Test Strategy: Doc review.
## Milestone 4: Auth, Header Navigation, and My Bots
Goal: add authenticated user flow and owned bot management UX.

- [x] `M4-T1` Finalize auth/session decisions and document constraints (owner: `main-agent`)
  - Subtasks:
  - Confirm local auth vs OAuth for this batch. Done: username/password only.
  - Confirm session model (cookie vs token) and protected route policy. Done: server-side session with `HttpOnly` secure cookies and route protection on My Bots/Lobby/seat select.
  - Record decisions in `PROJECT_SPEC.md` and `ARCHITECTURE.md`. Done.
  - Lock visibility/seating/leaderboard policy decisions. Done: private bots, public global leaderboard, multi-table seating per bot.
  - Lock bot isolation intent for bot-managed persistence. Done.
  - Acceptance: Auth decisions are explicit and unambiguous for implementation.
  - Test Strategy: Doc review checklist and architecture/spec consistency pass.
- [x] `M4-T2` Implement backend auth endpoints and protected-route dependency (owner: `feature-agent`)
  - Subtasks:
  - Add `POST /api/v1/auth/login`, `POST /api/v1/auth/logout`, `GET /api/v1/auth/me`.
  - Add persistent user storage and password/session handling.
  - Enforce auth dependency on My Bots, Lobby, and seat-selection endpoints.
  - Acceptance: Unauthenticated requests to protected endpoints are rejected; login session enables access.
  - Test Strategy: Backend integration tests for login, auth guard, and logout invalidation.
- [ ] `M4-T3` Implement frontend login page, protected app shell, and header menu (owner: `feature-agent`)
  - Subtasks:
  - Add login UI with validation and error handling.
  - Add shared authenticated header with `Lobby`, `My Bots`, and `Logout`.
  - Add route guard/redirect behavior for protected pages.
  - Acceptance: Protected pages are accessible only after login, with visible header navigation.
  - Test Strategy: Frontend smoke tests for redirect/login/logout/navigation flows.
- [ ] `M4-T4` Implement backend My Bots catalog APIs and artifact metadata storage (owner: `feature-agent`)
  - Subtasks:
  - Add `GET /api/v1/my/bots` and `POST /api/v1/my/bots`.
  - Persist bot ownership, metadata (`bot_id`, name, version, created_at), and artifact path.
  - Enforce ownership checks on bot listing and selection.
  - Acceptance: User sees only owned bots with stable metadata and upload validation feedback.
  - Test Strategy: Integration tests for list/upload authorization and invalid payloads.
- [ ] `M4-T5` Build My Bots frontend page with bot cards and upload flow (owner: `feature-agent`)
  - Subtasks:
  - Add list UI with bot container cards and required fields (`bot_id`, name, timestamps/status).
  - Add upload interaction and result states.
  - Add empty/loading/error states.
  - Acceptance: User can upload and then see bot card rendered with persisted metadata.
  - Test Strategy: Manual UI scenario test plus scripted frontend smoke checks.
- [ ] `M4-T6` Add seat flow support for selecting existing bot or inline upload (owner: `feature-agent`)
  - Subtasks:
  - Add `POST /api/v1/tables/{table_id}/seats/{seat_id}/bot-select`.
  - Update seat UI to choose from owned bots or upload directly.
  - Keep compatibility with existing match-start behavior.
  - Acceptance: Seating works through either select-existing or inline-upload without regressions.
  - Test Strategy: Integration tests for both seat paths and match start trigger.
- [ ] `M4-T7` Add test coverage for auth and bot-management flows (owner: `test-agent`)
  - Subtasks:
  - Add backend tests for auth/session lifecycle and My Bots ownership boundaries.
  - Add regression tests for seat select/upload branch behavior.
  - Add minimal frontend flow test coverage for login + My Bots.
  - Acceptance: New tests fail on auth/ownership regressions and pass on compliant behavior.
  - Test Strategy: Run backend `pytest` and selected frontend smoke tests in CI.
- [ ] `M4-T8` Review Milestone 4 changes for security and regression risk (owner: `review-agent`)
  - Subtasks:
  - Verify auth guard coverage and session invalidation behavior.
  - Verify ownership enforcement for all bot read/write/select paths.
  - Check backward compatibility of existing seat/match APIs.
  - Acceptance: No unresolved high-severity auth/ownership issues remain.
  - Test Strategy: Review checklist plus targeted endpoint retests.

## Milestone 5: Bot Isolation and Protocol v2
Goal: run bots in stronger isolation while providing complete table/player/action context.

- [ ] `M5-T1` Define protocol-v2 bot context schema and compatibility contract (owner: `main-agent`)
  - Subtasks:
  - Specify required context fields: player ids, seat map, stacks, pot, board, legal actions, prior actions.
  - Define versioning and backward compatibility behavior for legacy bots.
  - Document context size/timeout constraints.
  - Acceptance: Protocol schema is precise enough for backend and bot-template implementation.
  - Test Strategy: Schema review against existing bot contract and engine state availability.
- [ ] `M5-T2` Implement protocol adapter in backend bot runner path (owner: `feature-agent`)
  - Subtasks:
  - Map engine state to protocol-v2 structure for each decision.
  - Include full action timeline needed for opponent tracking.
  - Add protocol version in request payload to bot runtime.
  - Acceptance: Bots receive deterministic, complete context payload for every decision call.
  - Test Strategy: Unit tests for serializer completeness and field-level validation.
- [ ] `M5-T3` Implement isolated bot runtime supervisor with resource guards (owner: `feature-agent`)
  - Subtasks:
  - Execute bot code outside API process boundary.
  - Enforce timeout, memory, and failure containment policies.
  - Return normalized fallback action on runtime failure.
  - Acceptance: Bot crashes/timeouts are isolated and do not terminate API/match service.
  - Test Strategy: Integration tests with crashing, hanging, and malformed bots.
- [ ] `M5-T4` Update `bot_template/` for protocol-v2 usage guidance (owner: `feature-agent`)
  - Subtasks:
  - Update template contract docs and sample bot parser for new context fields.
  - Add examples for tracking opponent ids/actions from payload.
  - Document optional bot-local persistence expectations and limits.
  - Acceptance: Template lets developers build bots that can track all players and actions.
  - Test Strategy: Template smoke run with a sample hand context fixture.
- [ ] `M5-T5` Add dedicated isolation/protocol regression tests (owner: `test-agent`)
  - Subtasks:
  - Add tests for protocol completeness and stable field semantics.
  - Add tests for isolation guarantees under bot failures.
  - Add performance sanity checks for decision-call latency budget.
  - Acceptance: Regressions in protocol fields or isolation behavior are caught by automated tests.
  - Test Strategy: Backend `pytest` suite extensions with negative and stress-oriented fixtures.
- [ ] `M5-T6` Review Milestone 5 for sandbox and compatibility risks (owner: `review-agent`)
  - Subtasks:
  - Validate isolation boundary and guardrail enforcement paths.
  - Validate legacy bot fallback/compatibility behavior.
  - Validate protocol docs match runtime implementation.
  - Acceptance: No unresolved critical isolation/security issues remain.
  - Test Strategy: Review-driven targeted rerun of isolation and protocol tests.

## Milestone 6: Lobby, Multi-Table UX, and Persistent Leaderboard
Goal: replace single-table home with lobby + table pages and add persistent historical leaderboard.

- [ ] `M6-T1` Introduce persistent storage models/migrations for lobby and leaderboard entities (owner: `feature-agent`)
  - Subtasks:
  - Add persistent models for users, bots, tables, and leaderboard aggregates.
  - Add migration/bootstrap path for local/dev environments.
  - Keep compatibility with existing runtime hand history files.
  - Acceptance: Data survives process restarts and schema is reproducible in clean setup.
  - Test Strategy: Persistence integration test across app restart.
- [ ] `M6-T2` Implement lobby table list/create backend APIs (owner: `feature-agent`)
  - Subtasks:
  - Add `GET /api/v1/lobby/tables` and `POST /api/v1/lobby/tables`.
  - Return required table metadata for list rendering.
  - Enforce auth and input validation for creation flow.
  - Acceptance: Users can create tables and retrieve consistent lobby listings.
  - Test Strategy: API integration tests for create/list success and validation failures.
- [ ] `M6-T3` Implement leaderboard aggregation and read API (owner: `feature-agent`)
  - Subtasks:
  - Compute and persist `bb_won`, `hands_played`, and `bb/hand` per bot.
  - Update aggregates after each completed hand.
  - Add `GET /api/v1/lobby/leaderboard` sorted by `bb/hand`.
  - Acceptance: Leaderboard includes all historical participants with stable metrics.
  - Test Strategy: Integration tests for aggregate updates and ordering.
- [ ] `M6-T4` Build Lobby frontend page with table list/create and leaderboard (owner: `feature-agent`)
  - Subtasks:
  - Replace current main page with lobby list and create-table controls.
  - Add leaderboard panel with persistent bot rankings.
  - Add navigation from lobby rows to table detail page.
  - Acceptance: Lobby is default authenticated landing page with functional list/create/leaderboard.
  - Test Strategy: Frontend smoke test for list/create/navigation flows.
- [ ] `M6-T5` Implement table detail routing with existing live table experience (owner: `feature-agent`)
  - Subtasks:
  - Move current table UI into table-detail route/page.
  - Keep live hand summary, chart, and history interactions.
  - Ensure table route is keyed by `table_id`.
  - Acceptance: Opening a table from lobby shows existing gameplay panels for that table.
  - Test Strategy: Manual table route validation and API-driven smoke checks.
- [ ] `M6-T6` Add regression and edge-case tests for lobby/table/leaderboard flows (owner: `test-agent`)
  - Subtasks:
  - Add backend tests for multi-table lifecycle and scoreboard persistence.
  - Add tests for leaderboard with zero-hand and high-volume edge cases.
  - Add UI checks for table navigation and stale data handling.
  - Acceptance: Multi-table and leaderboard regressions are detected automatically.
  - Test Strategy: Extended backend `pytest` + frontend smoke suite in CI.
- [ ] `M6-T7` Review Milestone 6 for data consistency and UX regressions (owner: `review-agent`)
  - Subtasks:
  - Validate multi-table data isolation and routing correctness.
  - Validate leaderboard metric correctness and sorting semantics.
  - Validate no regressions in table gameplay/hand history behavior.
  - Acceptance: No unresolved high-severity consistency or regression issues remain.
  - Test Strategy: Review checklist plus targeted rerun of affected tests.
- [ ] `M6-T8` Run release readiness checks for Batch 2 scope (owner: `release-agent`)
  - Subtasks:
  - Run full repository validation and test suite.
  - Verify documentation and environment instructions match implemented behavior.
  - Summarize release blockers, residual risks, and deployment notes.
  - Acceptance: Batch 2 readiness report is published with clear go/no-go decision.
  - Test Strategy: End-to-end CI and local release checklist execution.
