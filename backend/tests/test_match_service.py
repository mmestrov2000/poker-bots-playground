import zipfile
from datetime import datetime, timezone
from pathlib import Path
from time import sleep

from app.services.match_service import HandRecord, MatchService
from app.storage.hand_store import HandStore


def _write_bot_zip(tmp_path: Path, name: str, body: str) -> Path:
    zip_path = tmp_path / name
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("bot.py", body)
    return zip_path


def test_registering_both_seats_starts_match(tmp_path: Path) -> None:
    service = MatchService(hand_store=HandStore(base_dir=tmp_path / "hands"))
    service.HAND_INTERVAL_SECONDS = 0.05

    bot_body = "\n".join(
        [
            "class PokerBot:",
            "    def act(self, state):",
            "        if 'check' in state.get('legal_actions', []):",
            "            return {'action': 'check'}",
            "        if 'call' in state.get('legal_actions', []):",
            "            return {'action': 'call'}",
            "        return {'action': 'fold'}",
        ]
    )
    bot_a = _write_bot_zip(tmp_path, "alpha.zip", bot_body)
    bot_b = _write_bot_zip(tmp_path, "beta.zip", bot_body)

    service.register_bot("A", "alpha.zip", bot_path=bot_a)
    service.register_bot("B", "beta.zip", bot_path=bot_b)

    match = service.get_match()
    assert match["status"] == "waiting"

    service.start_match()
    sleep(0.15)
    match = service.get_match()
    hands = service.list_hands(limit=10)

    assert match["status"] == "running"
    assert len(hands) >= 1

    latest_hand = service.get_hand(hands[0]["hand_id"])
    assert latest_hand is not None
    assert "Winner: Seat" in (latest_hand["history"] or "")

    service.pause_match()
    assert service.get_match()["status"] == "paused"

    service.resume_match()
    sleep(0.05)
    assert service.get_match()["status"] == "running"

    service.end_match()
    assert service.get_match()["status"] == "stopped"

    service.reset_match()


def test_reset_match_clears_state(tmp_path: Path) -> None:
    service = MatchService(hand_store=HandStore(base_dir=tmp_path / "hands"))
    service.HAND_INTERVAL_SECONDS = 0.05

    bot_body = "\n".join(
        [
            "class PokerBot:",
            "    def act(self, state):",
            "        if 'check' in state.get('legal_actions', []):",
            "            return {'action': 'check'}",
            "        if 'call' in state.get('legal_actions', []):",
            "            return {'action': 'call'}",
            "        return {'action': 'fold'}",
        ]
    )
    bot_a = _write_bot_zip(tmp_path, "alpha.zip", bot_body)
    bot_b = _write_bot_zip(tmp_path, "beta.zip", bot_body)

    service.register_bot("A", "alpha.zip", bot_path=bot_a)
    service.register_bot("B", "beta.zip", bot_path=bot_b)

    service.start_match()
    sleep(0.1)
    service.reset_match()

    match = service.get_match()
    seats = service.get_seats()

    assert match["status"] == "waiting"
    assert match["hands_played"] == 0
    assert all(not seat["ready"] for seat in seats)


def test_list_hands_paginates_with_snapshot(tmp_path: Path) -> None:
    service = MatchService(hand_store=HandStore(base_dir=tmp_path / "hands"))
    now = datetime.now(timezone.utc)
    with service._lock:
        service._hands = [
            HandRecord(
                hand_id=str(hand_id),
                completed_at=now,
                summary=f"Hand #{hand_id}",
                winner="A",
                pot=1.0,
                history_path=f"{hand_id}.txt",
            )
            for hand_id in range(1, 6)
        ]

    page_one = service.list_hands(page=1, page_size=2)
    assert [hand["hand_id"] for hand in page_one] == ["5", "4"]
    page_two = service.list_hands(page=2, page_size=2)
    assert [hand["hand_id"] for hand in page_two] == ["3", "2"]
    page_three = service.list_hands(page=3, page_size=2)
    assert [hand["hand_id"] for hand in page_three] == ["1"]

    snapshot_page = service.list_hands(page=1, page_size=2, max_hand_id=3)
    assert [hand["hand_id"] for hand in snapshot_page] == ["3", "2"]


def test_match_loop_runtime_error_stops_match_safely(tmp_path: Path) -> None:
    class ExplodingEngine:
        small_blind_cents = 50
        big_blind_cents = 100

        def play_hand(self, **kwargs):  # noqa: ANN003 - test double
            raise RuntimeError("engine failure")

    service = MatchService(
        hand_store=HandStore(base_dir=tmp_path / "hands"),
        engine=ExplodingEngine(),
    )
    service.HAND_INTERVAL_SECONDS = 0.01

    bot_body = "\n".join(
        [
            "class PokerBot:",
            "    def act(self, state):",
            "        return {'action': 'check'}",
        ]
    )
    bot_a = _write_bot_zip(tmp_path, "alpha.zip", bot_body)
    bot_b = _write_bot_zip(tmp_path, "beta.zip", bot_body)

    service.register_bot("A", "alpha.zip", bot_path=bot_a)
    service.register_bot("B", "beta.zip", bot_path=bot_b)

    service.start_match()
    sleep(0.05)
    match = service.get_match()
    assert match["status"] == "waiting"
    assert match["hands_played"] == 0
