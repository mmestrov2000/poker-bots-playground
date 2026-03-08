from __future__ import annotations

from pathlib import Path
from threading import Lock
from typing import Callable

from app.engine.game import PokerEngine
from app.services.match_service import HandRecord, MatchService
from app.storage.hand_store import HandStore


OnHandCompleted = Callable[[HandRecord, dict[str, str]], None]


class TableRuntimeManager:
    def __init__(
        self,
        *,
        hands_root: Path,
        on_hand_completed_factory: Callable[[str, float, float], OnHandCompleted | None] | None = None,
    ) -> None:
        self.hands_root = hands_root
        self.hands_root.mkdir(parents=True, exist_ok=True)
        self._on_hand_completed_factory = on_hand_completed_factory
        self._lock = Lock()
        self._services: dict[str, MatchService] = {}

    def get_or_create_service(
        self,
        *,
        table_id: str,
        small_blind: float,
        big_blind: float,
    ) -> MatchService:
        with self._lock:
            service = self._services.get(table_id)
            if service is not None:
                return service

            engine = PokerEngine(
                small_blind_cents=_blind_to_cents(small_blind),
                big_blind_cents=_blind_to_cents(big_blind),
            )
            callback = None
            if self._on_hand_completed_factory is not None:
                callback = self._on_hand_completed_factory(table_id, small_blind, big_blind)
            service = MatchService(
                table_id=table_id,
                hand_store=HandStore(base_dir=self.hands_root / table_id),
                engine=engine,
                on_hand_completed=callback,
            )
            self._services[table_id] = service
            return service

    def get_service_if_loaded(self, table_id: str) -> MatchService | None:
        with self._lock:
            return self._services.get(table_id)


def _blind_to_cents(value: float) -> int:
    return int(round(value * 100))
