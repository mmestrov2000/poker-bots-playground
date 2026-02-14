import io
import time
import zipfile
from datetime import datetime, timezone
from http.cookies import SimpleCookie
from pathlib import Path

import pytest
from fastapi import HTTPException, Response
from starlette.requests import Request

from app.api import routes
from app.services.match_service import HandRecord, MatchService
from app.auth.config import AuthSettings
from app.auth.service import AuthError, AuthLockedError
from app.auth.service import AuthService
from app.auth.store import AuthStore
from app.storage.hand_store import HandStore


class FakeUploadFile:
    def __init__(self, filename: str, payload: bytes):
        self.filename = filename
        self._payload = payload

    async def read(self) -> bytes:
        return self._payload


def build_zip(files: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def build_upload_file(filename: str, payload: bytes) -> FakeUploadFile:
    return FakeUploadFile(filename=filename, payload=payload)


@pytest.fixture(autouse=True)
def isolate_route_state(tmp_path, monkeypatch):
    uploads_dir = tmp_path / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    service = MatchService(hand_store=HandStore(base_dir=tmp_path / "hands"))
    service.HAND_INTERVAL_SECONDS = 0.01
    settings = AuthSettings(
        session_cookie_name="ppg_session",
        session_ttl_seconds=3600,
        login_max_failures=3,
        login_lockout_seconds=60,
        login_failure_window_seconds=300,
        bootstrap_username="bootstrap",
        bootstrap_password="bootstrap-password",
        db_path=Path(tmp_path / "auth.sqlite3"),
    )
    auth_service = AuthService(store=AuthStore(settings.db_path), settings=settings)
    auth_service.ensure_user("alice", "correct-horse-battery-staple")

    monkeypatch.setattr(routes, "uploads_dir", uploads_dir)
    monkeypatch.setattr(routes, "match_service", service)
    monkeypatch.setattr(routes, "auth_settings", settings)
    monkeypatch.setattr(routes, "auth_service", auth_service)
    yield
    service.reset_match()


def build_request_with_cookies(cookies: dict[str, str] | None = None) -> Request:
    headers: list[tuple[bytes, bytes]] = []
    if cookies:
        cookie_header = "; ".join(f"{k}={v}" for k, v in cookies.items())
        headers.append((b"cookie", cookie_header.encode("utf-8")))
    scope = {
        "type": "http",
        "asgi.version": "3.0",
        "method": "GET",
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "headers": headers,
    }
    return Request(scope)


def extract_session_cookie(response: Response) -> str:
    cookie = SimpleCookie()
    cookie.load(response.headers["set-cookie"])
    morsel = cookie[routes.auth_settings.session_cookie_name]
    return morsel.value


@pytest.mark.anyio
async def test_upload_rejects_invalid_seat():
    payload = build_zip({"bot.py": "class PokerBot: pass"})
    with pytest.raises(HTTPException) as exc_info:
        await routes.upload_bot("7", build_upload_file("bot.zip", payload))
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "seat_id must be 1-6"


@pytest.mark.anyio
async def test_upload_rejects_non_zip():
    with pytest.raises(HTTPException) as exc_info:
        await routes.upload_bot("1", build_upload_file("bot.txt", b"not a zip"))
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Only .zip bot uploads are supported"


@pytest.mark.anyio
async def test_upload_rejects_empty_payload():
    with pytest.raises(HTTPException) as exc_info:
        await routes.upload_bot("1", build_upload_file("bot.zip", b""))
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Upload payload is empty"


@pytest.mark.anyio
async def test_upload_rejects_payloads_over_size_limit():
    oversized_payload = b"x" * ((10 * 1024 * 1024) + 1)
    with pytest.raises(HTTPException) as exc_info:
        await routes.upload_bot("1", build_upload_file("bot.zip", oversized_payload))
    assert exc_info.value.status_code == 413
    assert exc_info.value.detail == "Upload exceeds 10MB limit"


@pytest.mark.anyio
async def test_upload_rejects_missing_bot_file():
    payload = build_zip({"readme.txt": "no bot here"})
    with pytest.raises(HTTPException) as exc_info:
        await routes.upload_bot("1", build_upload_file("bot.zip", payload))
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "bot.py must exist at zip root or one top-level folder"


@pytest.mark.anyio
async def test_upload_accepts_bot_file_in_single_top_level_folder():
    payload = build_zip(
        {
            "my_bot/bot.py": """
class PokerBot:
    def act(self, state):
        return {"action": "check", "amount": 0}
""",
        }
    )

    response = await routes.upload_bot("1", build_upload_file("nested.zip", payload))
    assert response["seat"]["ready"] is True
    assert response["seat"]["bot_name"] == "nested.zip"


@pytest.mark.anyio
async def test_upload_rejects_invalid_zip_archive():
    with pytest.raises(HTTPException) as exc_info:
        await routes.upload_bot("1", build_upload_file("bot.zip", b"not-a-real-zip"))
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Upload is not a valid zip archive"


@pytest.mark.anyio
async def test_upload_rejects_unsafe_archive_paths():
    payload = build_zip({"../bot.py": "class PokerBot: pass"})
    with pytest.raises(HTTPException) as exc_info:
        await routes.upload_bot("1", build_upload_file("bot.zip", payload))
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Archive contains unsafe paths"


@pytest.mark.anyio
async def test_upload_rejects_archives_with_multiple_bot_candidates():
    payload = build_zip(
        {
            "bot_a/bot.py": "class PokerBot: pass",
            "bot_b/bot.py": "class PokerBot: pass",
        }
    )
    with pytest.raises(HTTPException) as exc_info:
        await routes.upload_bot("1", build_upload_file("bot.zip", payload))
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Archive contains multiple bot.py candidates"


@pytest.mark.anyio
async def test_upload_rejects_archives_with_too_many_files():
    files = {f"file_{i}.txt": "x" for i in range(130)}
    files["bot.py"] = "class PokerBot:\n    def act(self, state):\n        return {'action': 'check'}"
    payload = build_zip(files)
    with pytest.raises(HTTPException) as exc_info:
        await routes.upload_bot("1", build_upload_file("bot.zip", payload))
    assert exc_info.value.status_code == 400
    assert "Archive contains too many files" in exc_info.value.detail


@pytest.mark.anyio
async def test_upload_rejects_large_bot_source_file():
    big_source = "class PokerBot:\n    pass\n" + ("#" * (256 * 1024))
    payload = build_zip({"bot.py": big_source})
    with pytest.raises(HTTPException) as exc_info:
        await routes.upload_bot("1", build_upload_file("bot.zip", payload))
    assert exc_info.value.status_code == 400
    assert "bot.py exceeds" in exc_info.value.detail


@pytest.mark.anyio
async def test_upload_rejects_missing_pokerbot_class():
    payload = build_zip({"bot.py": "class NotBot: pass"})
    with pytest.raises(HTTPException) as exc_info:
        await routes.upload_bot("1", build_upload_file("bot.zip", payload))
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "bot.py must define a PokerBot class"


@pytest.mark.anyio
async def test_uploads_start_match_and_expose_hands():
    payload = build_zip(
        {
            "bot.py": """
class PokerBot:
    def act(self, state):
        return {"action": "check", "amount": 0}
"""
        }
    )

    response_a = await routes.upload_bot("1", build_upload_file("alpha.zip", payload))
    assert response_a["seat"]["ready"] is True
    assert response_a["match"]["status"] == "waiting"

    response_b = await routes.upload_bot("2", build_upload_file("beta.zip", payload))
    assert response_b["match"]["status"] == "waiting"

    start_response = routes.start_match()
    assert start_response["match"]["status"] == "running"

    deadline = time.monotonic() + 2.0
    hands: list[dict] = []
    hands_response: dict = {}
    while time.monotonic() < deadline:
        hands_response = routes.list_hands(page=1, page_size=5)
        hands = hands_response["hands"]
        if hands:
            break
        time.sleep(0.05)

    assert hands, "Expected at least one hand to be generated"
    assert hands_response["page"] == 1
    assert hands_response["page_size"] == 5
    assert hands_response["total_hands"] >= len(hands)
    assert hands_response["total_pages"] >= 1

    snapshot_response = routes.list_hands(page=1, page_size=1, max_hand_id=1)
    assert snapshot_response["total_hands"] == 1
    assert snapshot_response["hands"][0]["hand_id"] == "1"

    latest_hand_id = hands[0]["hand_id"]
    detail = routes.get_hand(latest_hand_id)
    assert detail["hand_id"] == latest_hand_id
    assert detail["history"]

    pause_response = routes.pause_match()
    assert pause_response["match"]["status"] == "paused"

    resume_response = routes.resume_match()
    assert resume_response["match"]["status"] == "running"

    end_response = routes.end_match()
    assert end_response["match"]["status"] == "stopped"

    reset_response = routes.reset_match()
    assert reset_response["match"]["status"] == "waiting"
    assert all(not seat["ready"] for seat in routes.get_seats()["seats"])
    assert routes.list_hands(page=1, page_size=5)["hands"] == []


def test_get_pnl_returns_entries_and_last_hand_id():
    service = routes.match_service
    now = datetime.now(timezone.utc)
    with service._lock:
        service._hands = [
            HandRecord(
                hand_id="1",
                completed_at=now,
                summary="Hand #1",
                winners=["1"],
                pot=1.0,
                history_path="1.txt",
                deltas={
                    "1": 1.0,
                    "2": -1.0,
                    "3": 0.0,
                    "4": 0.0,
                    "5": 0.0,
                    "6": 0.0,
                },
                active_seats=["1", "2"],
            ),
            HandRecord(
                hand_id="2",
                completed_at=now,
                summary="Hand #2",
                winners=["2"],
                pot=2.5,
                history_path="2.txt",
                deltas={
                    "1": -2.5,
                    "2": 2.5,
                    "3": 0.0,
                    "4": 0.0,
                    "5": 0.0,
                    "6": 0.0,
                },
                active_seats=["1", "2"],
            ),
        ]

    response = routes.get_pnl()
    assert response["last_hand_id"] == 2
    assert response["entries"] == [
        {
            "hand_id": 1,
            "deltas": {
                "1": 1.0,
                "2": -1.0,
                "3": 0.0,
                "4": 0.0,
                "5": 0.0,
                "6": 0.0,
            },
        },
        {
            "hand_id": 2,
            "deltas": {
                "1": -2.5,
                "2": 2.5,
                "3": 0.0,
                "4": 0.0,
                "5": 0.0,
                "6": 0.0,
            },
        },
    ]

    response = routes.get_pnl(since_hand_id=1)
    assert response["entries"] == [
        {
            "hand_id": 2,
            "deltas": {
                "1": -2.5,
                "2": 2.5,
                "3": 0.0,
                "4": 0.0,
                "5": 0.0,
                "6": 0.0,
            },
        }
    ]


def test_get_hand_returns_404_for_unknown_hand():
    with pytest.raises(HTTPException) as exc_info:
        routes.get_hand("missing-hand")
    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Hand not found"


def test_auth_login_success_and_me_returns_user():
    response = Response()
    payload = routes.LoginRequest(username="alice", password="correct-horse-battery-staple")
    login_result = routes.login(payload, response)
    assert login_result["user"]["username"] == "alice"
    session_id = extract_session_cookie(response)
    assert session_id

    request = build_request_with_cookies({routes.auth_settings.session_cookie_name: session_id})
    me_response = routes.me(current_user=routes.require_authenticated_user(request))
    assert me_response["user"]["username"] == "alice"


def test_auth_register_success_sets_session_and_me_returns_user():
    response = Response()
    payload = routes.RegisterRequest(username="new-player", password="new-password")
    register_result = routes.register(payload, response)
    assert register_result["user"]["username"] == "new-player"
    session_id = extract_session_cookie(response)
    assert session_id

    request = build_request_with_cookies({routes.auth_settings.session_cookie_name: session_id})
    me_response = routes.me(current_user=routes.require_authenticated_user(request))
    assert me_response["user"]["username"] == "new-player"


def test_auth_register_duplicate_username_returns_409():
    with pytest.raises(HTTPException) as exc_info:
        routes.register(
            routes.RegisterRequest(username="alice", password="anything"),
            Response(),
        )
    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "Username is already taken"


def test_auth_login_failure_returns_401():
    with pytest.raises(HTTPException) as exc_info:
        routes.login(
            routes.LoginRequest(username="alice", password="wrong-password"),
            Response(),
        )
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid username or password"


def test_protected_route_rejects_without_auth():
    with pytest.raises(HTTPException) as exc_info:
        routes.require_authenticated_user(build_request_with_cookies())
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Authentication required"


def test_logout_invalidates_session():
    response = Response()
    login_result = routes.login(
        routes.LoginRequest(username="alice", password="correct-horse-battery-staple"),
        response,
    )
    assert login_result["user"]["username"] == "alice"
    session_id = extract_session_cookie(response)

    logout_request = build_request_with_cookies({routes.auth_settings.session_cookie_name: session_id})
    logout_response = Response()
    result = routes.logout(logout_request, logout_response)
    assert result["ok"] is True

    with pytest.raises(HTTPException) as exc_info:
        routes.require_authenticated_user(logout_request)
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Authentication required"


def test_login_bruteforce_lockout_behavior():
    for _ in range(2):
        with pytest.raises(AuthError):
            routes.auth_service.login(username="alice", password="wrong-password")

    with pytest.raises(AuthLockedError) as lockout_error:
        routes.auth_service.login(username="alice", password="wrong-password")
    assert lockout_error.value.retry_after_seconds > 0

    with pytest.raises(AuthLockedError):
        routes.auth_service.login(username="alice", password="correct-horse-battery-staple")
