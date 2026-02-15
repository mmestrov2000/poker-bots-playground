from __future__ import annotations

import json
from pathlib import Path
from typing import Any

BOT_PROTOCOL_VERSION = "2.0"


class PokerBot:
    """Protocol-v2 starter bot for the poker playground."""

    protocol_version = "2.0"

    def __init__(self) -> None:
        self.opponent_stats: dict[str, dict[str, int]] = {}
        self._last_history_index = -1

    def act(self, state: dict[str, Any]) -> dict[str, Any]:
        if state.get("protocol_version") != "2.0":
            return self._act_legacy(state)

        hero_player_id = state.get("hero", {}).get("player_id")
        legal_actions = self._normalize_legal_actions(state.get("legal_actions", []))
        self._track_players(state.get("players", []), hero_player_id)
        self._track_actions(state.get("action_history", []), hero_player_id)
        return self._choose_action(
            legal_actions=legal_actions,
            big_blind=state.get("table", {}).get("big_blind", 0),
        )

    def _act_legacy(self, state: dict[str, Any]) -> dict[str, Any]:
        legal_actions = state.get("legal_actions", ["check"])
        if "check" in legal_actions:
            return {"action": "check"}
        if "call" in legal_actions:
            return {"action": "call"}
        if "fold" in legal_actions:
            return {"action": "fold"}
        fallback_action = legal_actions[0] if legal_actions else "fold"
        return {"action": fallback_action}

    def _normalize_legal_actions(self, legal_actions: list[Any]) -> dict[str, dict[str, Any]]:
        normalized: dict[str, dict[str, Any]] = {}
        for entry in legal_actions:
            if isinstance(entry, str):
                normalized[entry] = {"action": entry}
                continue
            if isinstance(entry, dict) and isinstance(entry.get("action"), str):
                normalized[entry["action"]] = entry
        return normalized

    def _track_players(self, players: list[Any], hero_player_id: str | None) -> None:
        for player in players:
            if not isinstance(player, dict):
                continue
            player_id = player.get("player_id")
            if not isinstance(player_id, str) or player_id == hero_player_id:
                continue
            self.opponent_stats.setdefault(
                player_id,
                {"actions": 0, "aggressive_actions": 0, "last_seen_stack": 0},
            )
            stack = player.get("stack")
            if isinstance(stack, int):
                self.opponent_stats[player_id]["last_seen_stack"] = stack

    def _track_actions(self, history: list[Any], hero_player_id: str | None) -> None:
        for event in history:
            if not isinstance(event, dict):
                continue
            index = event.get("index")
            if not isinstance(index, int) or index <= self._last_history_index:
                continue
            self._last_history_index = index

            player_id = event.get("player_id")
            if not isinstance(player_id, str) or player_id == hero_player_id:
                continue
            stats = self.opponent_stats.setdefault(
                player_id,
                {"actions": 0, "aggressive_actions": 0, "last_seen_stack": 0},
            )
            stats["actions"] += 1
            if event.get("action") in {"bet", "raise"}:
                stats["aggressive_actions"] += 1

    def _choose_action(self, *, legal_actions: dict[str, dict[str, Any]], big_blind: int) -> dict[str, Any]:
        if "check" in legal_actions:
            return {"action": "check"}

        call_entry = legal_actions.get("call")
        if call_entry is not None:
            call_amount = call_entry.get("min_amount", 0)
            if isinstance(call_amount, int) and call_amount <= max(1, big_blind):
                return {"action": "call"}

        raise_entry = legal_actions.get("raise") or legal_actions.get("bet")
        if raise_entry is not None and self._opponents_are_passive():
            amount = raise_entry.get("min_amount")
            if isinstance(amount, int):
                return {"action": raise_entry["action"], "amount": amount}

        if "fold" in legal_actions:
            return {"action": "fold"}

        fallback = next(iter(legal_actions.values()), {"action": "fold"})
        response: dict[str, Any] = {"action": fallback["action"]}
        amount = fallback.get("min_amount")
        if response["action"] in {"bet", "raise"} and isinstance(amount, int):
            response["amount"] = amount
        return response

    def _opponents_are_passive(self) -> bool:
        for stats in self.opponent_stats.values():
            if stats["actions"] == 0:
                continue
            if stats["aggressive_actions"] * 2 > stats["actions"]:
                return False
        return True

    def save_local_state(self, path: str = "bot_local_state.json") -> None:
        data = {
            "last_history_index": self._last_history_index,
            "opponent_stats": self.opponent_stats,
        }
        Path(path).write_text(json.dumps(data), encoding="utf-8")

    def load_local_state(self, path: str = "bot_local_state.json") -> None:
        source = Path(path)
        if not source.exists():
            return
        payload = json.loads(source.read_text(encoding="utf-8"))
        self._last_history_index = int(payload.get("last_history_index", -1))
        stats = payload.get("opponent_stats", {})
        if isinstance(stats, dict):
            self.opponent_stats = {
                str(player_id): {
                    "actions": int(values.get("actions", 0)),
                    "aggressive_actions": int(values.get("aggressive_actions", 0)),
                    "last_seen_stack": int(values.get("last_seen_stack", 0)),
                }
                for player_id, values in stats.items()
                if isinstance(values, dict)
            }
