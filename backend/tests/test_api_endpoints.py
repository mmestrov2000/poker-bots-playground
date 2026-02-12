import io
import time
import zipfile
from datetime import datetime, timezone

import pytest
from fastapi import HTTPException

from app.api import routes
from app.bots.registry import BotRegistry
from app.bots.security import MAX_REQUIREMENTS_BYTES
from app.services.match_service import HandRecord, MatchService
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
    artifacts_dir = tmp_path / "artifacts"
    cache_dir = tmp_path / "artifact-cache"
    service = MatchService(hand_store=HandStore(base_dir=tmp_path / "hands"))
    service.HAND_INTERVAL_SECONDS = 0.01
    registry = BotRegistry(path=tmp_path / "bots" / "registry.json")

    monkeypatch.setattr(routes, "match_service", service)
    monkeypatch.setattr(routes, "bot_registry", registry)
    monkeypatch.setattr(routes, "_shared_bootstrapped", False)
    monkeypatch.delenv("DB_HOST", raising=False)
    monkeypatch.setenv("DB_ENABLED", "0")
    monkeypatch.setenv("BOT_ARTIFACT_BACKEND", "filesystem")
    monkeypatch.setenv("BOT_ARTIFACTS_DIR", str(artifacts_dir))
    monkeypatch.setenv("BOT_ARTIFACT_CACHE_DIR", str(cache_dir))
    monkeypatch.setenv("BOT_EXECUTION_MODE", "local")
    yield
    service.reset_match()


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
    assert response["seat"]["bot_id"]


@pytest.mark.anyio
async def test_upload_accepts_requirements_txt():
    payload = build_zip(
        {
            "bot.py": """
class PokerBot:
    def act(self, state):
        return {"action": "check", "amount": 0}
""",
            "requirements.txt": "requests==2.32.3",
        }
    )

    response = await routes.upload_bot("1", build_upload_file("deps.zip", payload))
    assert response["seat"]["ready"] is True


@pytest.mark.anyio
async def test_upload_rejects_multiple_requirements_candidates():
    payload = build_zip(
        {
            "bot.py": "class PokerBot: pass",
            "requirements.txt": "requests==2.32.3",
            "nested/requirements.txt": "httpx==0.28.1",
        }
    )
    with pytest.raises(HTTPException) as exc_info:
        await routes.upload_bot("1", build_upload_file("deps.zip", payload))
    assert exc_info.value.status_code == 400
    assert "requirements.txt candidates" in exc_info.value.detail


@pytest.mark.anyio
async def test_upload_rejects_large_requirements():
    payload = build_zip(
        {
            "bot.py": "class PokerBot: pass",
            "requirements.txt": "x" * (MAX_REQUIREMENTS_BYTES + 1),
        }
    )
    with pytest.raises(HTTPException) as exc_info:
        await routes.upload_bot("1", build_upload_file("deps.zip", payload))
    assert exc_info.value.status_code == 400
    assert "requirements.txt exceeds" in exc_info.value.detail


@pytest.mark.anyio
async def test_upload_creates_registry_entry_with_stable_password():
    payload = build_zip(
        {
            "bot.py": """
class PokerBot:
    def act(self, state):
        return {"action": "check", "amount": 0}
"""
        }
    )
    response = await routes.upload_bot("1", build_upload_file("alpha.zip", payload))
    bot_id = response["seat"]["bot_id"]
    entry = routes.bot_registry.get(bot_id)
    assert entry is not None
    assert entry["bot_name"] == "alpha.zip"
    assert entry["schema"] == f"bot_{bot_id}"
    assert entry["db_user"] == f"bot_{bot_id}_rw"
    first_password = entry["db_password"]

    response_second = await routes.upload_bot("2", build_upload_file("alpha.zip", payload))
    assert response_second["seat"]["bot_id"] == bot_id
    entry_second = routes.bot_registry.get(bot_id)
    assert entry_second["db_password"] == first_password


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


@pytest.mark.anyio
async def test_db_info_returns_registry_details():
    payload = build_zip(
        {
            "bot.py": """
class PokerBot:
    def act(self, state):
        return {"action": "check", "amount": 0}
"""
        }
    )
    response = await routes.upload_bot("1", build_upload_file("alpha.zip", payload))
    bot_id = response["seat"]["bot_id"]
    info = routes.get_db_info(bot_id)
    assert info["schema"] == f"bot_{bot_id}"
    assert info["user"] == f"bot_{bot_id}_rw"
    assert info["enabled"] is False
    assert info["shared_schema"] == "shared"
    assert info["password"]


def test_db_info_unknown_bot_raises_404():
    with pytest.raises(HTTPException) as exc_info:
        routes.get_db_info("missing-bot")
    assert exc_info.value.status_code == 404
