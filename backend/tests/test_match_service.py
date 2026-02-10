from pathlib import Path
from time import sleep

from app.services.match_service import MatchService
from app.storage.hand_store import HandStore


def test_registering_both_seats_starts_match(tmp_path: Path) -> None:
    service = MatchService(hand_store=HandStore(base_dir=tmp_path / "hands"))
    service.HAND_INTERVAL_SECONDS = 0.05

    service.register_bot("A", "alpha.zip")
    service.register_bot("B", "beta.zip")

    sleep(0.15)
    match = service.get_match()
    hands = service.list_hands(limit=10)

    assert match["status"] == "running"
    assert len(hands) >= 1

    latest_hand = service.get_hand(hands[-1]["hand_id"])
    assert latest_hand is not None
    assert "Winner: Seat" in (latest_hand["history"] or "")

    service.reset_match()


def test_reset_match_clears_state(tmp_path: Path) -> None:
    service = MatchService(hand_store=HandStore(base_dir=tmp_path / "hands"))
    service.HAND_INTERVAL_SECONDS = 0.05

    service.register_bot("A", "alpha.zip")
    service.register_bot("B", "beta.zip")

    sleep(0.1)
    service.reset_match()

    match = service.get_match()
    seats = service.get_seats()

    assert match["status"] == "waiting"
    assert match["hands_played"] == 0
    assert all(not seat["ready"] for seat in seats)
