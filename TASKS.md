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
- [ ] `M1-T6` Review M1 implementation changes and request fixes (owner: `review-agent`)
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
- [ ] `M2-T6` Review M2 API/UI changes and call out regressions (owner: `review-agent`)
  - Acceptance: Review feedback is documented and blocking issues are resolved before merge.
  - Test Strategy: Manual API/UI verification against acceptance criteria.

## Milestone 3: Quality, Hardening, and Release
Goal: make MVP stable and deploy-ready.

- [x] `M3-T1` Add comprehensive backend test suite for engine and API (owner: `test-agent`)
  - Acceptance: Critical flows and failure paths are covered.
  - Test Strategy: `pytest` suite green locally and in CI.
- [ ] `M3-T2` Add bot upload constraints and runtime safeguards (owner: `feature-agent`)
  - Acceptance: Upload size limits, extension checks, and execution guardrails are enforced.
  - Test Strategy: Negative tests for oversized and malformed uploads.
- [ ] `M3-T3` Finalize Docker image and compose workflow (owner: `feature-agent`)
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
