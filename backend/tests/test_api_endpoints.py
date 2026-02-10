import io
import time
import zipfile

import pytest
from fastapi.testclient import TestClient

from app.api.routes import match_service
from app.main import create_app


def build_zip(files: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def upload_bot(client: TestClient, seat_id: str, payload: bytes, filename: str = "bot.zip"):
    return client.post(
        f"/api/v1/seats/{seat_id}/bot",
        files={"bot_file": (filename, payload, "application/zip")},
    )


@pytest.fixture(autouse=True)
def reset_match_state():
    match_service.HAND_INTERVAL_SECONDS = 0.01
    match_service.reset_match()
    yield
    match_service.reset_match()


@pytest.fixture()
def client():
    return TestClient(create_app())


def test_upload_rejects_invalid_seat(client: TestClient):
    payload = build_zip({"bot.py": "class PokerBot: pass"})
    response = upload_bot(client, "C", payload)
    assert response.status_code == 400
    assert response.json()["detail"] == "seat_id must be A or B"


def test_upload_rejects_non_zip(client: TestClient):
    response = client.post(
        "/api/v1/seats/A/bot",
        files={"bot_file": ("bot.txt", b"not a zip", "text/plain")},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Only .zip bot uploads are supported"


def test_upload_rejects_missing_bot_file(client: TestClient):
    payload = build_zip({"readme.txt": "no bot here"})
    response = upload_bot(client, "A", payload)
    assert response.status_code == 400
    assert response.json()["detail"] == "bot.py must be at the root of the zip"


def test_upload_rejects_missing_pokerbot_class(client: TestClient):
    payload = build_zip({"bot.py": "class NotBot: pass"})
    response = upload_bot(client, "A", payload)
    assert response.status_code == 400
    assert response.json()["detail"] == "bot.py must define a PokerBot class"


def test_uploads_start_match_and_expose_hands(client: TestClient):
    payload = build_zip(
        {
            "bot.py": """
class PokerBot:
    def act(self, state):
        return {\"action\": \"check\", \"amount\": 0}
"""
        }
    )

    response_a = upload_bot(client, "A", payload)
    assert response_a.status_code == 200
    assert response_a.json()["seat"]["ready"] is True
    assert response_a.json()["match"]["status"] == "waiting"

    response_b = upload_bot(client, "B", payload)
    assert response_b.status_code == 200
    assert response_b.json()["match"]["status"] == "running"

    deadline = time.monotonic() + 2.0
    hands = []
    while time.monotonic() < deadline:
        hands_response = client.get("/api/v1/hands?limit=5")
        assert hands_response.status_code == 200
        hands = hands_response.json()["hands"]
        if hands:
            break
        time.sleep(0.05)

    assert hands, "Expected at least one hand to be generated"

    latest_hand_id = hands[-1]["hand_id"]
    detail_response = client.get(f"/api/v1/hands/{latest_hand_id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["hand_id"] == latest_hand_id
    assert detail["history"]

    reset_response = client.post("/api/v1/match/reset")
    assert reset_response.status_code == 200
    assert reset_response.json()["match"]["status"] == "waiting"

    seats_response = client.get("/api/v1/seats")
    assert seats_response.status_code == 200
    for seat in seats_response.json()["seats"]:
        assert seat["ready"] is False

    hands_after_reset = client.get("/api/v1/hands?limit=5")
    assert hands_after_reset.status_code == 200
    assert hands_after_reset.json()["hands"] == []
