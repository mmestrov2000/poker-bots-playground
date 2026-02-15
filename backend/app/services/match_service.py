from pathlib import Path
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Event, Lock, Thread, current_thread
from typing import Literal

from app.bots.loader import load_bot_from_zip
from app.bots.protocol import resolve_bot_protocol
from app.bots.runtime import BotRunner
from app.engine.game import PokerEngine, SeatId, SEAT_ORDER, order_seats
from app.engine.hand_history import format_hand_history
from app.storage.hand_store import HandStore


MatchStatus = Literal["waiting", "running", "paused", "stopped"]


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
    winners: list[SeatId]
    pot: float
    history_path: str
    deltas: dict[SeatId, float]
    active_seats: list[SeatId]

    def to_summary_dict(self) -> dict:
        return {
            "hand_id": self.hand_id,
            "completed_at": self.completed_at.isoformat(),
            "summary": self.summary,
            "winners": self.winners,
            "pot": self.pot,
        }


class MatchService:
    HAND_INTERVAL_SECONDS = 1.0

    def __init__(self, hand_store: HandStore, engine: PokerEngine | None = None) -> None:
        self.hand_store = hand_store
        self.engine = engine or PokerEngine()
        self._lock = Lock()
        self._stop_event = Event()
        self._loop_thread: Thread | None = None
        self._status: MatchStatus = "waiting"
        self._started_at: datetime | None = None
        self._hands: list[HandRecord] = []
        self._hand_counter = 0
        self._button_seat: SeatId | None = None
        self._seats: dict[SeatId, SeatState] = {
            seat_id: SeatState(seat_id=seat_id) for seat_id in SEAT_ORDER
        }
        self._bots: dict[SeatId, BotRunner | None] = {seat_id: None for seat_id in SEAT_ORDER}

    def get_seats(self) -> list[dict]:
        with self._lock:
            return [self._seats[seat_id].to_dict() for seat_id in SEAT_ORDER]

    def get_match(self) -> dict:
        with self._lock:
            return {
                "status": self._status,
                "started_at": self._started_at.isoformat() if self._started_at else None,
                "hands_played": len(self._hands),
                "last_hand_id": self._hands[-1].hand_id if self._hands else None,
            }

    def list_hands(
        self,
        limit: int | None = None,
        page: int = 1,
        page_size: int = 100,
        max_hand_id: int | None = None,
    ) -> list[dict]:
        with self._lock:
            total_hands = len(self._hands)
            snapshot_count = total_hands if max_hand_id is None else min(max_hand_id, total_hands)
            if limit is not None:
                page_size = limit
                page = 1
            if page_size < 1 or snapshot_count == 0:
                return []
            start = max(snapshot_count - (page * page_size), 0)
            end = snapshot_count - (page - 1) * page_size
            if end <= 0 or start >= snapshot_count:
                return []
            page_records = self._hands[start:end]
            return [record.to_summary_dict() for record in reversed(page_records)]

    def list_pnl(self, since_hand_id: int | None = None) -> tuple[list[dict], int | None]:
        with self._lock:
            if not self._hands:
                return [], None
            entries: list[dict] = []
            last_hand_id: int | None = None
            for record in self._hands:
                try:
                    hand_number = int(record.hand_id)
                except ValueError:
                    continue
                last_hand_id = hand_number
                if since_hand_id is not None and hand_number <= since_hand_id:
                    continue
                entries.append({"hand_id": hand_number, "deltas": record.deltas})
            return entries, last_hand_id

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
            "winners": record.winners,
            "pot": record.pot,
            "history": history_text,
        }

    def register_bot(self, seat_id: SeatId, bot_name: str, bot_path: Path | None = None) -> dict:
        if seat_id not in self._seats:
            raise ValueError(f"Invalid seat id: {seat_id}")

        now = datetime.now(timezone.utc)
        with self._lock:
            if bot_path is not None:
                bot_instance = load_bot_from_zip(bot_path)
                self._bots[seat_id] = BotRunner(
                    bot=bot_instance,
                    seat_id=seat_id,
                    protocol_version=resolve_bot_protocol(bot_instance),
                )
            seat = self._seats[seat_id]
            seat.ready = True
            seat.bot_name = bot_name
            seat.uploaded_at = now

            return seat.to_dict()

    def start_match(self) -> None:
        now = datetime.now(timezone.utc)
        with self._lock:
            if self._status == "running":
                raise RuntimeError("Match already running")
            if self._status == "paused":
                raise RuntimeError("Match is paused; use resume")
            if len(self._ready_seats_locked()) < 2:
                raise RuntimeError("At least two seats must be ready to start")
            previous_status = self._status
            self._status = "running"
            if previous_status in {"waiting", "stopped"} or self._started_at is None:
                self._started_at = now
            self._ensure_loop_running_locked()

    def pause_match(self) -> None:
        thread: Thread | None
        with self._lock:
            if self._status != "running":
                raise RuntimeError("Match is not running")
            self._status = "paused"
            self._stop_event.set()
            thread = self._loop_thread
            self._loop_thread = None
        if thread and thread.is_alive() and thread is not current_thread():
            thread.join(timeout=2)

    def resume_match(self) -> None:
        with self._lock:
            if self._status != "paused":
                raise RuntimeError("Match is not paused")
            if len(self._ready_seats_locked()) < 2:
                raise RuntimeError("At least two seats must be ready to resume")
            self._status = "running"
            if self._started_at is None:
                self._started_at = datetime.now(timezone.utc)
            self._ensure_loop_running_locked()

    def end_match(self) -> None:
        thread: Thread | None
        with self._lock:
            if self._status not in {"running", "paused"}:
                raise RuntimeError("Match is not running")
            self._status = "stopped"
            self._stop_event.set()
            thread = self._loop_thread
            self._loop_thread = None
        if thread and thread.is_alive() and thread is not current_thread():
            thread.join(timeout=2)

    def reset_match(self) -> None:
        thread: Thread | None
        with self._lock:
            self._status = "waiting"
            self._started_at = None
            self._hands.clear()
            self._hand_counter = 0
            self._button_seat = None
            self._seats = {
                seat_id: SeatState(seat_id=seat_id) for seat_id in SEAT_ORDER
            }
            self._bots = {seat_id: None for seat_id in SEAT_ORDER}
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
            try:
                with self._lock:
                    if self._status != "running":
                        return
                    self._simulate_hand_locked()
            except Exception:  # noqa: BLE001 - runtime safeguard for untrusted bot failures
                with self._lock:
                    self._status = "waiting"
                    self._started_at = None
                self._stop_event.set()
                return
            self._stop_event.wait(self.HAND_INTERVAL_SECONDS)

    def _simulate_hand_locked(self) -> None:
        self._hand_counter += 1
        hand_id = str(self._hand_counter)
        active_seats = self._ready_seats_locked()
        if len(active_seats) < 2:
            self._status = "waiting"
            self._started_at = None
            return

        button = self._next_button_seat(active_seats)
        self._button_seat = button

        seat_names = {
            seat_id: self._seats[seat_id].bot_name or f"Seat{seat_id}-Bot"
            for seat_id in active_seats
        }
        bots = {
            seat_id: bot for seat_id, bot in self._bots.items() if seat_id in active_seats
        }
        if any(bot is None for bot in bots.values()):
            raise RuntimeError("match loop started without loaded bots")

        result = self.engine.play_hand(
            hand_id=hand_id,
            bots=bots,
            seat_names=seat_names,
            button=button,
        )
        history = format_hand_history(
            hand_id=hand_id,
            winners=result.winners,
            pot_size_cents=result.pot_cents,
            seat_names=seat_names,
            button=button,
            hole_cards=result.hole_cards,
            board=result.board,
            actions=result.actions,
            small_blind_cents=self.engine.small_blind_cents,
            big_blind_cents=self.engine.big_blind_cents,
        )
        history_path = self.hand_store.save_hand(hand_id, history)

        pot_size = result.pot_cents / 100
        winners_label = ", ".join(f"Seat {seat}" for seat in result.winners)
        if len(result.winners) == 1:
            summary = f"Hand #{hand_id}: {winners_label} won ${pot_size:.2f}"
        else:
            summary = f"Hand #{hand_id}: {winners_label} split ${pot_size:.2f}"
        deltas = {seat_id: 0.0 for seat_id in SEAT_ORDER}
        for seat_id, delta_cents in result.deltas.items():
            deltas[seat_id] = delta_cents / 100
        self._hands.append(
            HandRecord(
                hand_id=hand_id,
                completed_at=datetime.now(timezone.utc),
                summary=summary,
                winners=result.winners,
                pot=pot_size,
                history_path=str(history_path),
                deltas=deltas,
                active_seats=active_seats,
            )
        )

    def get_leaderboard(self) -> dict:
        with self._lock:
            big_blind = self.engine.big_blind_cents / 100
            stats = {
                seat_id: {
                    "seat_id": seat_id,
                    "bot_name": self._seats[seat_id].bot_name,
                    "hands_played": 0,
                    "total_bb": 0.0,
                    "bb_per_hand": 0.0,
                }
                for seat_id in SEAT_ORDER
            }
            for record in self._hands:
                for seat_id in record.active_seats:
                    stats[seat_id]["hands_played"] += 1
                for seat_id, delta in record.deltas.items():
                    if big_blind:
                        stats[seat_id]["total_bb"] += delta / big_blind
            leaders = [
                stat
                for stat in stats.values()
                if stat["bot_name"]
            ]
            for stat in leaders:
                hands = stat["hands_played"]
                stat["bb_per_hand"] = stat["total_bb"] / hands if hands else 0.0
            leaders.sort(
                key=lambda item: (item["bb_per_hand"], item["hands_played"]),
                reverse=True,
            )
            return {"leaders": leaders, "big_blind": big_blind}

    def _ready_seats_locked(self) -> list[SeatId]:
        ready = [
            seat_id
            for seat_id, seat in self._seats.items()
            if seat.ready and self._bots[seat_id] is not None
        ]
        return order_seats(ready)

    def _next_button_seat(self, active_seats: list[SeatId]) -> SeatId:
        if self._button_seat not in active_seats:
            return active_seats[0]
        index = active_seats.index(self._button_seat)
        return active_seats[(index + 1) % len(active_seats)]
