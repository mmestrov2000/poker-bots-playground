import io
import time
import zipfile

import pytest
from fastapi import HTTPException

from app.api import routes
from app.services.match_service import MatchService
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

    monkeypatch.setattr(routes, "uploads_dir", uploads_dir)
    monkeypatch.setattr(routes, "match_service", service)
    yield
    service.reset_match()


@pytest.mark.anyio
async def test_upload_rejects_invalid_seat():
    payload = build_zip({"bot.py": "class PokerBot: pass"})
    with pytest.raises(HTTPException) as exc_info:
        await routes.upload_bot("C", build_upload_file("bot.zip", payload))
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "seat_id must be A or B"


@pytest.mark.anyio
async def test_upload_rejects_non_zip():
    with pytest.raises(HTTPException) as exc_info:
        await routes.upload_bot("A", build_upload_file("bot.txt", b"not a zip"))
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Only .zip bot uploads are supported"


@pytest.mark.anyio
async def test_upload_rejects_empty_payload():
    with pytest.raises(HTTPException) as exc_info:
        await routes.upload_bot("A", build_upload_file("bot.zip", b""))
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Upload payload is empty"


@pytest.mark.anyio
async def test_upload_rejects_payloads_over_size_limit():
    oversized_payload = b"x" * ((10 * 1024 * 1024) + 1)
    with pytest.raises(HTTPException) as exc_info:
        await routes.upload_bot("A", build_upload_file("bot.zip", oversized_payload))
    assert exc_info.value.status_code == 413
    assert exc_info.value.detail == "Upload exceeds 10MB limit"


@pytest.mark.anyio
async def test_upload_rejects_missing_bot_file():
    payload = build_zip({"readme.txt": "no bot here"})
    with pytest.raises(HTTPException) as exc_info:
        await routes.upload_bot("A", build_upload_file("bot.zip", payload))
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

    response = await routes.upload_bot("A", build_upload_file("nested.zip", payload))
    assert response["seat"]["ready"] is True
    assert response["seat"]["bot_name"] == "nested.zip"


@pytest.mark.anyio
async def test_upload_rejects_invalid_zip_archive():
    with pytest.raises(HTTPException) as exc_info:
        await routes.upload_bot("A", build_upload_file("bot.zip", b"not-a-real-zip"))
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Upload is not a valid zip archive"


@pytest.mark.anyio
async def test_upload_rejects_unsafe_archive_paths():
    payload = build_zip({"../bot.py": "class PokerBot: pass"})
    with pytest.raises(HTTPException) as exc_info:
        await routes.upload_bot("A", build_upload_file("bot.zip", payload))
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
        await routes.upload_bot("A", build_upload_file("bot.zip", payload))
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Archive contains multiple bot.py candidates"


@pytest.mark.anyio
async def test_upload_rejects_archives_with_too_many_files():
    files = {f"file_{i}.txt": "x" for i in range(130)}
    files["bot.py"] = "class PokerBot:\n    def act(self, state):\n        return {'action': 'check'}"
    payload = build_zip(files)
    with pytest.raises(HTTPException) as exc_info:
        await routes.upload_bot("A", build_upload_file("bot.zip", payload))
    assert exc_info.value.status_code == 400
    assert "Archive contains too many files" in exc_info.value.detail


@pytest.mark.anyio
async def test_upload_rejects_large_bot_source_file():
    big_source = "class PokerBot:\n    pass\n" + ("#" * (256 * 1024))
    payload = build_zip({"bot.py": big_source})
    with pytest.raises(HTTPException) as exc_info:
        await routes.upload_bot("A", build_upload_file("bot.zip", payload))
    assert exc_info.value.status_code == 400
    assert "bot.py exceeds" in exc_info.value.detail


@pytest.mark.anyio
async def test_upload_rejects_missing_pokerbot_class():
    payload = build_zip({"bot.py": "class NotBot: pass"})
    with pytest.raises(HTTPException) as exc_info:
        await routes.upload_bot("A", build_upload_file("bot.zip", payload))
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

    response_a = await routes.upload_bot("A", build_upload_file("alpha.zip", payload))
    assert response_a["seat"]["ready"] is True
    assert response_a["match"]["status"] == "waiting"

    response_b = await routes.upload_bot("B", build_upload_file("beta.zip", payload))
    assert response_b["match"]["status"] == "waiting"

    start_response = routes.start_match()
    assert start_response["match"]["status"] == "running"

    deadline = time.monotonic() + 2.0
    hands: list[dict] = []
    while time.monotonic() < deadline:
        hands = routes.list_hands(limit=5)["hands"]
        if hands:
            break
        time.sleep(0.05)

    assert hands, "Expected at least one hand to be generated"

    latest_hand_id = hands[-1]["hand_id"]
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
    assert routes.list_hands(limit=5)["hands"] == []


def test_get_hand_returns_404_for_unknown_hand():
    with pytest.raises(HTTPException) as exc_info:
        routes.get_hand("missing-hand")
    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == "Hand not found"
