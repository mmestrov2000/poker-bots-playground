from dataclasses import dataclass
from datetime import datetime, timezone
from random import SystemRandom
from threading import Event, Lock, Thread, current_thread
from typing import Literal

from app.engine.hand_history import format_hand_history
from app.storage.hand_store import HandStore


SeatId = Literal["A", "B"]


@dataclass
class SeatState:
    seat_id: SeatId
    ready: bool = False
    bot_name: str | None = None
    uploaded_at: datetime | None = None

    def to_dict(self) -> dict:
        return {
            "seat_id": self.seat_id,
            "ready": self.ready,
            "bot_name": self.bot_name,
            "uploaded_at": self.uploaded_at.isoformat() if self.uploaded_at else None,
        }


@dataclass
class HandRecord:
    hand_id: str
    completed_at: datetime
    summary: str
    winner: SeatId
    pot: float
    history_path: str

    def to_summary_dict(self) -> dict:
        return {
            "hand_id": self.hand_id,
            "completed_at": self.completed_at.isoformat(),
            "summary": self.summary,
            "winner": self.winner,
            "pot": self.pot,
        }


class MatchService:
    HAND_INTERVAL_SECONDS = 1.0

    def __init__(self, hand_store: HandStore) -> None:
        self.hand_store = hand_store
        self._random = SystemRandom()
        self._lock = Lock()
        self._stop_event = Event()
        self._loop_thread: Thread | None = None
        self._status: Literal["waiting", "running"] = "waiting"
        self._started_at: datetime | None = None
        self._hands: list[HandRecord] = []
        self._hand_counter = 0
        self._seats: dict[SeatId, SeatState] = {
            "A": SeatState(seat_id="A"),
            "B": SeatState(seat_id="B"),
        }

    def get_seats(self) -> list[dict]:
        with self._lock:
            return [self._seats["A"].to_dict(), self._seats["B"].to_dict()]

    def get_match(self) -> dict:
        with self._lock:
            return {
                "status": self._status,
                "started_at": self._started_at.isoformat() if self._started_at else None,
                "hands_played": len(self._hands),
                "last_hand_id": self._hands[-1].hand_id if self._hands else None,
            }

    def list_hands(self, limit: int = 50) -> list[dict]:
        with self._lock:
            return [record.to_summary_dict() for record in self._hands[-limit:]]

    def get_hand(self, hand_id: str) -> dict | None:
        with self._lock:
            record = next((h for h in self._hands if h.hand_id == hand_id), None)
            if not record:
                return None
        history_text = self.hand_store.load_hand(hand_id)
        return {
            "hand_id": record.hand_id,
            "completed_at": record.completed_at.isoformat(),
            "summary": record.summary,
            "winner": record.winner,
            "pot": record.pot,
            "history": history_text,
        }

    def register_bot(self, seat_id: SeatId, bot_name: str) -> dict:
        if seat_id not in self._seats:
            raise ValueError(f"Invalid seat id: {seat_id}")

        now = datetime.now(timezone.utc)
        with self._lock:
            seat = self._seats[seat_id]
            seat.ready = True
            seat.bot_name = bot_name
            seat.uploaded_at = now

            if self._seats["A"].ready and self._seats["B"].ready:
                if self._status != "running":
                    self._status = "running"
                    self._started_at = now
                    self._ensure_loop_running_locked()

            return seat.to_dict()

    def reset_match(self) -> None:
        thread: Thread | None
        with self._lock:
            self._status = "waiting"
            self._started_at = None
            self._hands.clear()
            self._hand_counter = 0
            self._seats = {
                "A": SeatState(seat_id="A"),
                "B": SeatState(seat_id="B"),
            }
            self._stop_event.set()
            thread = self._loop_thread
            self._loop_thread = None

        if thread and thread.is_alive() and thread is not current_thread():
            thread.join(timeout=2)

        self.hand_store.clear()

    def _ensure_loop_running_locked(self) -> None:
        if self._loop_thread and self._loop_thread.is_alive():
            return
        self._stop_event.clear()
        self._loop_thread = Thread(target=self._run_match_loop, daemon=True, name="match-loop")
        self._loop_thread.start()

    def _run_match_loop(self) -> None:
        while not self._stop_event.is_set():
            with self._lock:
                if self._status != "running":
                    return
                self._simulate_hand_locked()
            self._stop_event.wait(self.HAND_INTERVAL_SECONDS)

    def _simulate_hand_locked(self) -> None:
        self._hand_counter += 1
        hand_id = str(self._hand_counter)
        winner: SeatId = self._random.choice(["A", "B"])
        pot_size = round(self._random.uniform(1.5, 25.0), 2)
        seat_a_name = self._seats["A"].bot_name or "SeatA-Bot"
        seat_b_name = self._seats["B"].bot_name or "SeatB-Bot"

        history = format_hand_history(
            hand_id=hand_id,
            winner=winner,
            pot_size=pot_size,
            seat_a_name=seat_a_name,
            seat_b_name=seat_b_name,
        )
        history_path = self.hand_store.save_hand(hand_id, history)

        summary = f"Hand #{hand_id}: Seat {winner} won {pot_size:.2f} BB"
        self._hands.append(
            HandRecord(
                hand_id=hand_id,
                completed_at=datetime.now(timezone.utc),
                summary=summary,
                winner=winner,
                pot=pot_size,
                history_path=str(history_path),
            )
        )
