import io
import math
import stat
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
        session_cookie_secure=None,
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
    service._on_hand_completed = routes._update_persistent_leaderboard
    yield
    service.reset_match()


def build_request_with_cookies(
    cookies: dict[str, str] | None = None,
    host: str = "localhost",
    scheme: str = "http",
    extra_headers: list[tuple[bytes, bytes]] | None = None,
) -> Request:
    headers: list[tuple[bytes, bytes]] = []
    headers.append((b"host", host.encode("utf-8")))
    if cookies:
        cookie_header = "; ".join(f"{k}={v}" for k, v in cookies.items())
        headers.append((b"cookie", cookie_header.encode("utf-8")))
    if extra_headers:
        headers.extend(extra_headers)
    scope = {
        "type": "http",
        "asgi.version": "3.0",
        "scheme": scheme,
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


def extract_cookie_morsel(response: Response):
    cookie = SimpleCookie()
    cookie.load(response.headers["set-cookie"])
    return cookie[routes.auth_settings.session_cookie_name]


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
    login_result = routes.login(payload, response, build_request_with_cookies())
    assert login_result["user"]["username"] == "alice"
    session_id = extract_session_cookie(response)
    assert session_id

    request = build_request_with_cookies({routes.auth_settings.session_cookie_name: session_id})
    me_response = routes.me(current_user=routes.require_authenticated_user(request))
    assert me_response["user"]["username"] == "alice"


@pytest.mark.anyio
async def test_my_bots_upload_and_list_success_for_authenticated_user():
    current_user = routes.auth_service.ensure_user("alice", "correct-horse-battery-staple")
    payload = build_zip(
        {
            "bot.py": """
class PokerBot:
    def act(self, state):
        return {"action": "check", "amount": 0}
""",
        }
    )

    created = await routes.upload_my_bot(
        current_user=current_user,
        bot_file=build_upload_file("alpha.zip", payload),
        name="Alpha",
        version="1.2.3",
    )

    bot = created["bot"]
    assert bot["bot_id"]
    assert bot["owner_user_id"] == current_user["user_id"]
    assert bot["name"] == "Alpha"
    assert bot["version"] == "1.2.3"
    assert bot["status"] == "ready"
    assert "artifact_path" not in bot

    listed = routes.list_my_bots(current_user=current_user)
    assert len(listed["bots"]) == 1
    assert listed["bots"][0]["bot_id"] == bot["bot_id"]


def test_my_bots_endpoints_reject_unauthenticated_access():
    with pytest.raises(HTTPException) as exc_info:
        routes.require_authenticated_user(build_request_with_cookies())
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Authentication required"


def test_lobby_tables_list_and_create_success():
    alice = routes.auth_service.ensure_user("alice", "correct-horse-battery-staple")
    bob = routes.auth_service.ensure_user("bob", "correct-horse-battery-staple")

    created = routes.create_lobby_table(
        payload=routes.CreateLobbyTableRequest(small_blind=0.5, big_blind=1.0),
        current_user=alice,
    )
    table = created["table"]
    assert table["table_id"]
    assert table["small_blind"] == 0.5
    assert table["big_blind"] == 1.0
    assert table["status"] == "waiting"
    assert table["state"] == "waiting"
    assert table["seats_filled"] == 0
    assert table["max_seats"] == 6
    assert datetime.fromisoformat(table["created_at"]).tzinfo is not None
    assert "created_by_user_id" not in table

    listed = routes.list_lobby_tables(current_user=bob)
    assert len(listed["tables"]) == 1
    listed_table = listed["tables"][0]
    assert listed_table["table_id"] == table["table_id"]
    assert listed_table["small_blind"] == 0.5
    assert listed_table["big_blind"] == 1.0
    assert listed_table["status"] == "waiting"
    assert listed_table["state"] == "waiting"
    assert listed_table["seats_filled"] == 0
    assert listed_table["max_seats"] == 6
    assert datetime.fromisoformat(listed_table["created_at"]).tzinfo is not None


def test_lobby_tables_create_rejects_invalid_blinds():
    current_user = routes.auth_service.ensure_user("alice", "correct-horse-battery-staple")

    with pytest.raises(HTTPException) as bad_blinds:
        routes.create_lobby_table(
            payload=routes.CreateLobbyTableRequest(small_blind=1.0, big_blind=1.0),
            current_user=current_user,
        )
    assert bad_blinds.value.status_code == 400
    assert bad_blinds.value.detail == "big_blind must be greater than small_blind"


def test_lobby_tables_support_multi_table_lifecycle_listing():
    alice = routes.auth_service.ensure_user("alice", "correct-horse-battery-staple")
    bob = routes.auth_service.ensure_user("bob", "correct-horse-battery-staple")

    created_alpha = routes.create_lobby_table(
        payload=routes.CreateLobbyTableRequest(small_blind=0.5, big_blind=1.0),
        current_user=alice,
    )["table"]
    created_beta = routes.create_lobby_table(
        payload=routes.CreateLobbyTableRequest(small_blind=1.0, big_blind=2.0),
        current_user=bob,
    )["table"]
    created_gamma = routes.create_lobby_table(
        payload=routes.CreateLobbyTableRequest(small_blind=2.0, big_blind=4.0),
        current_user=alice,
    )["table"]

    listed = routes.list_lobby_tables(current_user=alice)["tables"]
    listed_by_id = {table["table_id"]: table for table in listed}
    created_ids = {
        created_alpha["table_id"],
        created_beta["table_id"],
        created_gamma["table_id"],
    }

    assert set(listed_by_id) == created_ids
    for table_id in created_ids:
        assert listed_by_id[table_id]["status"] == "waiting"
        assert listed_by_id[table_id]["seats_filled"] == 0
        assert listed_by_id[table_id]["max_seats"] == 6


@pytest.mark.anyio
async def test_my_bots_ownership_isolated_between_users():
    alice = routes.auth_service.ensure_user("alice", "correct-horse-battery-staple")
    bob = routes.auth_service.ensure_user("bob", "correct-horse-battery-staple")
    payload = build_zip(
        {
            "bot.py": """
class PokerBot:
    def act(self, state):
        return {"action": "check", "amount": 0}
""",
        }
    )

    alice_bot = await routes.upload_my_bot(
        current_user=alice,
        bot_file=build_upload_file("alice.zip", payload),
        name="Alice Bot",
        version="1.0.0",
    )
    bob_bot = await routes.upload_my_bot(
        current_user=bob,
        bot_file=build_upload_file("bob.zip", payload),
        name="Bob Bot",
        version="2.0.0",
    )

    alice_list = routes.list_my_bots(current_user=alice)["bots"]
    bob_list = routes.list_my_bots(current_user=bob)["bots"]
    assert [bot["bot_id"] for bot in alice_list] == [alice_bot["bot"]["bot_id"]]
    assert [bot["bot_id"] for bot in bob_list] == [bob_bot["bot"]["bot_id"]]

    with pytest.raises(HTTPException) as forbidden:
        routes.require_owned_bot(bob_bot["bot"]["bot_id"], current_user=alice)
    assert forbidden.value.status_code == 403
    assert forbidden.value.detail == "Forbidden"


@pytest.mark.anyio
async def test_my_bots_upload_rejects_invalid_payload():
    current_user = routes.auth_service.ensure_user("alice", "correct-horse-battery-staple")

    with pytest.raises(HTTPException) as non_zip:
        await routes.upload_my_bot(
            current_user=current_user,
            bot_file=build_upload_file("bad.txt", b"not-zip"),
            name="Bad",
            version="1.0.0",
        )
    assert non_zip.value.status_code == 400
    assert non_zip.value.detail == "Only .zip bot uploads are supported"

    with pytest.raises(HTTPException) as empty_name:
        await routes.upload_my_bot(
            current_user=current_user,
            bot_file=build_upload_file("bot.zip", build_zip({"bot.py": "class PokerBot: pass"})),
            name="   ",
            version="1.0.0",
        )
    assert empty_name.value.status_code == 400
    assert empty_name.value.detail == "name is required"

    with pytest.raises(HTTPException) as invalid_archive:
        await routes.upload_my_bot(
            current_user=current_user,
            bot_file=build_upload_file("bot.zip", b"not-a-real-zip"),
            name="Broken Bot",
            version="1.0.0",
        )
    assert invalid_archive.value.status_code == 400
    assert invalid_archive.value.detail == "Upload is not a valid zip archive"


@pytest.mark.anyio
async def test_seat_bot_select_supports_existing_owned_bot():
    current_user = routes.auth_service.ensure_user("alice", "correct-horse-battery-staple")
    payload = build_zip(
        {
            "bot.py": """
class PokerBot:
    def act(self, state):
        return {"action": "check", "amount": 0}
"""
        }
    )
    created = await routes.upload_my_bot(
        current_user=current_user,
        bot_file=build_upload_file("alpha.zip", payload),
        name="Alpha",
        version="1.0.0",
    )

    response = routes.select_bot_for_seat(
        table_id="default",
        seat_id="1",
        payload=routes.SelectBotRequest(bot_id=created["bot"]["bot_id"]),
        current_user=current_user,
    )
    assert response["seat"]["seat_id"] == "1"
    assert response["seat"]["ready"] is True
    assert response["seat"]["bot_name"] == "Alpha"
    assert response["match"]["status"] == "waiting"


@pytest.mark.anyio
async def test_seat_bot_select_requires_ownership_and_valid_payload():
    alice = routes.auth_service.ensure_user("alice", "correct-horse-battery-staple")
    bob = routes.auth_service.ensure_user("bob", "correct-horse-battery-staple")
    payload = build_zip(
        {
            "bot.py": """
class PokerBot:
    def act(self, state):
        return {"action": "check", "amount": 0}
"""
        }
    )
    created = await routes.upload_my_bot(
        current_user=bob,
        bot_file=build_upload_file("bob.zip", payload),
        name="Bob Bot",
        version="2.0.0",
    )

    with pytest.raises(HTTPException) as missing_payload:
        routes.select_bot_for_seat(
            table_id="default",
            seat_id="1",
            payload=None,
            current_user=alice,
        )
    assert missing_payload.value.status_code == 400
    assert missing_payload.value.detail == "bot_id is required"

    with pytest.raises(HTTPException) as invalid_seat:
        routes.select_bot_for_seat(
            table_id="default",
            seat_id="A",
            payload=routes.SelectBotRequest(bot_id=created["bot"]["bot_id"]),
            current_user=alice,
        )
    assert invalid_seat.value.status_code == 400
    assert invalid_seat.value.detail == "seat_id must be 1-6"

    with pytest.raises(HTTPException) as forbidden:
        routes.select_bot_for_seat(
            table_id="default",
            seat_id="1",
            payload=routes.SelectBotRequest(bot_id=created["bot"]["bot_id"]),
            current_user=alice,
        )
    assert forbidden.value.status_code == 403
    assert forbidden.value.detail == "Forbidden"


@pytest.mark.anyio
async def test_lobby_leaderboard_updates_after_completed_hand():
    current_user = routes.auth_service.ensure_user("alice", "correct-horse-battery-staple")
    payload = build_zip(
        {
            "bot.py": """
class PokerBot:
    def act(self, state):
        return {"action": "check", "amount": 0}
"""
        }
    )
    alpha = await routes.upload_my_bot(
        current_user=current_user,
        bot_file=build_upload_file("alpha.zip", payload),
        name="Alpha",
        version="1.0.0",
    )
    beta = await routes.upload_my_bot(
        current_user=current_user,
        bot_file=build_upload_file("beta.zip", payload),
        name="Beta",
        version="1.0.0",
    )
    routes.select_bot_for_seat(
        table_id="default",
        seat_id="1",
        payload=routes.SelectBotRequest(bot_id=alpha["bot"]["bot_id"]),
        current_user=current_user,
    )
    routes.select_bot_for_seat(
        table_id="default",
        seat_id="2",
        payload=routes.SelectBotRequest(bot_id=beta["bot"]["bot_id"]),
        current_user=current_user,
    )

    with routes.match_service._lock:
        routes.match_service._simulate_hand_locked()

    leaderboard = routes.get_lobby_leaderboard(current_user=current_user)["leaderboard"]
    by_bot = {entry["bot_id"]: entry for entry in leaderboard}
    assert set(by_bot) == {alpha["bot"]["bot_id"], beta["bot"]["bot_id"]}
    assert by_bot[alpha["bot"]["bot_id"]]["hands_played"] == 1
    assert by_bot[beta["bot"]["bot_id"]]["hands_played"] == 1
    assert (
        by_bot[alpha["bot"]["bot_id"]]["bb_won"]
        + by_bot[beta["bot"]["bot_id"]]["bb_won"]
        == pytest.approx(0.0, abs=1e-9)
    )


@pytest.mark.anyio
async def test_lobby_leaderboard_is_sorted_by_bb_per_hand():
    current_user = routes.auth_service.ensure_user("alice", "correct-horse-battery-staple")
    payload = build_zip(
        {
            "bot.py": """
class PokerBot:
    def act(self, state):
        return {"action": "check", "amount": 0}
"""
        }
    )
    alpha = await routes.upload_my_bot(
        current_user=current_user,
        bot_file=build_upload_file("alpha.zip", payload),
        name="Alpha",
        version="1.0.0",
    )
    beta = await routes.upload_my_bot(
        current_user=current_user,
        bot_file=build_upload_file("beta.zip", payload),
        name="Beta",
        version="1.0.0",
    )
    gamma = await routes.upload_my_bot(
        current_user=current_user,
        bot_file=build_upload_file("gamma.zip", payload),
        name="Gamma",
        version="1.0.0",
    )
    routes.auth_service.store.upsert_leaderboard_row(
        bot_id=alpha["bot"]["bot_id"],
        hands_played=10,
        bb_won=25.0,
        updated_at=1700000010,
    )
    routes.auth_service.store.upsert_leaderboard_row(
        bot_id=beta["bot"]["bot_id"],
        hands_played=10,
        bb_won=5.0,
        updated_at=1700000011,
    )
    routes.auth_service.store.upsert_leaderboard_row(
        bot_id=gamma["bot"]["bot_id"],
        hands_played=20,
        bb_won=5.0,
        updated_at=1700000012,
    )

    leaderboard = routes.get_lobby_leaderboard(current_user=current_user)["leaderboard"]
    assert [entry["bot_id"] for entry in leaderboard] == [
        alpha["bot"]["bot_id"],
        beta["bot"]["bot_id"],
        gamma["bot"]["bot_id"],
    ]


def test_lobby_leaderboard_handles_zero_hand_and_high_volume_rows():
    current_user = routes.auth_service.ensure_user("alice", "correct-horse-battery-staple")
    now_ts = int(datetime.now(timezone.utc).timestamp())
    store = routes.auth_service.store

    store.create_bot_record(
        bot_id="bot-zero",
        owner_user_id=current_user["user_id"],
        name="Zero",
        version="1.0.0",
        artifact_path="/tmp/zero.zip",
        now_ts=now_ts,
    )
    store.create_bot_record(
        bot_id="bot-hi-pos",
        owner_user_id=current_user["user_id"],
        name="High Positive",
        version="1.0.0",
        artifact_path="/tmp/hi-pos.zip",
        now_ts=now_ts + 1,
    )
    store.create_bot_record(
        bot_id="bot-hi-neg",
        owner_user_id=current_user["user_id"],
        name="High Negative",
        version="1.0.0",
        artifact_path="/tmp/hi-neg.zip",
        now_ts=now_ts + 2,
    )

    store.upsert_leaderboard_row(
        bot_id="bot-zero",
        hands_played=0,
        bb_won=999999.0,
        updated_at=now_ts + 3,
    )
    store.upsert_leaderboard_row(
        bot_id="bot-hi-pos",
        hands_played=1_000_000,
        bb_won=25000.0,
        updated_at=now_ts + 4,
    )
    store.upsert_leaderboard_row(
        bot_id="bot-hi-neg",
        hands_played=2_000_000,
        bb_won=-10000.0,
        updated_at=now_ts + 5,
    )

    leaderboard = routes.get_lobby_leaderboard(current_user=current_user)["leaderboard"]
    rows = {entry["bot_id"]: entry for entry in leaderboard}

    assert [entry["bot_id"] for entry in leaderboard] == ["bot-hi-pos", "bot-zero", "bot-hi-neg"]
    assert rows["bot-zero"]["hands_played"] == 0
    assert rows["bot-zero"]["bb_per_hand"] == 0.0
    assert math.isfinite(rows["bot-hi-pos"]["bb_per_hand"])
    assert rows["bot-hi-pos"]["bb_per_hand"] == pytest.approx(0.025)
    assert rows["bot-hi-neg"]["bb_per_hand"] == pytest.approx(-0.005)


def test_lobby_leaderboard_persists_across_auth_service_restart():
    current_user = routes.auth_service.ensure_user("alice", "correct-horse-battery-staple")
    now_ts = int(datetime.now(timezone.utc).timestamp())

    routes.auth_service.store.create_bot_record(
        bot_id="persisted-bot",
        owner_user_id=current_user["user_id"],
        name="Persisted",
        version="1.0.0",
        artifact_path="/tmp/persisted.zip",
        now_ts=now_ts,
    )
    routes.auth_service.store.upsert_leaderboard_row(
        bot_id="persisted-bot",
        hands_played=42,
        bb_won=10.5,
        updated_at=now_ts + 1,
    )

    original_auth_service = routes.auth_service
    restarted_auth_service = AuthService(
        store=AuthStore(routes.auth_settings.db_path),
        settings=routes.auth_settings,
    )
    routes.auth_service = restarted_auth_service
    try:
        leaderboard = routes.get_lobby_leaderboard(current_user=current_user)["leaderboard"]
    finally:
        routes.auth_service = original_auth_service

    persisted = next(entry for entry in leaderboard if entry["bot_id"] == "persisted-bot")
    assert persisted["bot_name"] == "Persisted"
    assert persisted["hands_played"] == 42
    assert persisted["bb_won"] == pytest.approx(10.5)
    assert persisted["bb_per_hand"] == pytest.approx(0.25)


def test_auth_register_success_sets_session_and_me_returns_user():
    response = Response()
    payload = routes.RegisterRequest(username="new-player", password="new-password")
    register_result = routes.register(payload, response, build_request_with_cookies())
    assert register_result["user"]["username"] == "new-player"
    session_id = extract_session_cookie(response)
    assert session_id

    request = build_request_with_cookies({routes.auth_settings.session_cookie_name: session_id})
    me_response = routes.me(current_user=routes.require_authenticated_user(request))
    assert me_response["user"]["username"] == "new-player"


def test_auth_register_duplicate_username_returns_409():
    with pytest.raises(HTTPException) as exc_info:
        routes.register(
            routes.RegisterRequest(username="alice", password="anything-long"),
            Response(),
            build_request_with_cookies(),
        )
    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "Username is already taken"


def test_auth_login_failure_returns_401():
    with pytest.raises(HTTPException) as exc_info:
        routes.login(
            routes.LoginRequest(username="alice", password="wrong-password"),
            Response(),
            build_request_with_cookies(),
        )
    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid username or password"


@pytest.mark.anyio
async def test_inline_upload_and_seat_selection_do_not_auto_start_match():
    current_user = routes.auth_service.ensure_user("alice", "correct-horse-battery-staple")
    payload = build_zip(
        {
            "bot.py": """
class PokerBot:
    def act(self, state):
        return {"action": "check", "amount": 0}
"""
        }
    )
    alpha = await routes.upload_my_bot(
        current_user=current_user,
        bot_file=build_upload_file("alpha.zip", payload),
        name="Alpha",
        version="1.0.0",
    )
    beta = await routes.upload_my_bot(
        current_user=current_user,
        bot_file=build_upload_file("beta.zip", payload),
        name="Beta",
        version="2.0.0",
    )

    first_select = routes.select_bot_for_seat(
        table_id="default",
        seat_id="1",
        payload=routes.SelectBotRequest(bot_id=alpha["bot"]["bot_id"]),
        current_user=current_user,
    )
    second_select = routes.select_bot_for_seat(
        table_id="default",
        seat_id="2",
        payload=routes.SelectBotRequest(bot_id=beta["bot"]["bot_id"]),
        current_user=current_user,
    )
    assert first_select["match"]["status"] == "waiting"
    assert second_select["match"]["status"] == "waiting"

    before_start = routes.get_match()
    assert before_start["match"]["status"] == "waiting"

    started = routes.start_match()
    assert started["match"]["status"] == "running"


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
        build_request_with_cookies(),
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


def test_auth_cookie_secure_flag_is_disabled_for_local_http():
    response = Response()
    routes.login(
        routes.LoginRequest(username="alice", password="correct-horse-battery-staple"),
        response,
        build_request_with_cookies(host="localhost", scheme="http"),
    )
    morsel = extract_cookie_morsel(response)
    assert not morsel["secure"]


def test_auth_cookie_secure_flag_is_enabled_for_forwarded_https():
    response = Response()
    routes.login(
        routes.LoginRequest(username="alice", password="correct-horse-battery-staple"),
        response,
        build_request_with_cookies(
            host="example.com",
            scheme="http",
            extra_headers=[(b"x-forwarded-proto", b"https")],
        ),
    )
    morsel = extract_cookie_morsel(response)
    assert bool(morsel["secure"])


def test_registered_users_persist_across_auth_service_restart(tmp_path):
    db_path = tmp_path / "auth.sqlite3"
    settings = AuthSettings(
        session_cookie_name="ppg_session",
        session_cookie_secure=None,
        session_ttl_seconds=3600,
        login_max_failures=3,
        login_lockout_seconds=60,
        login_failure_window_seconds=300,
        bootstrap_username="bootstrap",
        bootstrap_password="bootstrap-password",
        db_path=db_path,
    )

    first_service = AuthService(store=AuthStore(db_path), settings=settings)
    first_service.register(username="durable-user", password="super-long-password")

    restarted_service = AuthService(store=AuthStore(db_path), settings=settings)
    user, _session = restarted_service.login(
        username="durable-user",
        password="super-long-password",
    )
    assert user["username"] == "durable-user"


def test_auth_database_file_permissions_are_restricted(tmp_path):
    db_path = tmp_path / "auth.sqlite3"
    settings = AuthSettings(
        session_cookie_name="ppg_session",
        session_cookie_secure=None,
        session_ttl_seconds=3600,
        login_max_failures=3,
        login_lockout_seconds=60,
        login_failure_window_seconds=300,
        bootstrap_username="bootstrap",
        bootstrap_password="bootstrap-password",
        db_path=db_path,
    )

    service = AuthService(store=AuthStore(db_path), settings=settings)
    service.register(username="perm-user", password="another-long-password")

    # db file is created immediately; wal/shm are optional depending on sqlite behavior.
    db_mode = stat.S_IMODE(db_path.stat().st_mode)
    assert db_mode == 0o600
