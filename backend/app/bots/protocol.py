from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

SeatId = str
Card = Any
ActionEvent = Any

PROTOCOL_V2 = "2.0"


def normalize_protocol_value(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return str(value)
    normalized = value.strip()
    return normalized or None


def build_decision_state(
    *,
    table_id: str,
    hand_id: str,
    seat: SeatId,
    street: str,
    hole_cards: list[Card],
    board: list[Card],
    pot: int,
    stack: int,
    to_call: int,
    min_raise_to: int,
    legal_actions: list[str],
    seat_name: str,
    seats: list[SeatId],
    seat_names: dict[SeatId, str],
    stacks: dict[SeatId, int],
    bets: dict[SeatId, int],
    folded: set[SeatId],
    button: SeatId,
    small_blind: SeatId,
    big_blind: SeatId,
    small_blind_amount: int,
    big_blind_amount: int,
    actions: list[ActionEvent],
) -> dict:
    del stack
    del small_blind
    del big_blind

    seat_to_player = {seat_id: f"player-{seat_id}" for seat_id in seats}
    max_raise_to = bets[seat] + stacks[seat]
    history = _build_action_history(actions=actions, seat_to_player=seat_to_player)

    state: dict[str, Any] = {
        "protocol_version": PROTOCOL_V2,
        "decision_id": f"{table_id}:{hand_id}:{street}:{seat}:{len(history)}",
        "table": {
            "table_id": table_id,
            "hand_id": hand_id,
            "street": street,
            "button_seat": button,
            "small_blind": small_blind_amount,
            "big_blind": big_blind_amount,
        },
        "hero": {
            "player_id": seat_to_player[seat],
            "seat_id": seat,
            "name": seat_names[seat],
            "hole_cards": [str(card) for card in hole_cards],
            "stack": stacks[seat],
            "bet": bets[seat],
            "to_call": to_call,
            "min_raise_to": min_raise_to,
            "max_raise_to": max_raise_to,
        },
        "players": [
            {
                "player_id": seat_to_player[seat_id],
                "seat_id": seat_id,
                "name": seat_names[seat_id],
                "stack": stacks[seat_id],
                "bet": bets[seat_id],
                "folded": seat_id in folded,
                "all_in": stacks[seat_id] == 0,
                "is_hero": seat_id == seat,
            }
            for seat_id in seats
        ],
        "board": {
            "cards": [str(card) for card in board],
            "pot": pot,
        },
        "legal_actions": _build_legal_actions(
            legal_actions=legal_actions,
            to_call=to_call,
            min_raise_to=min_raise_to,
            max_raise_to=max_raise_to,
        ),
        "action_history": history,
    }
    state["meta"] = {
        "server_time": datetime.now(timezone.utc).isoformat(),
        "state_bytes": 0,
    }
    state_bytes = _serialized_size(state)
    while True:
        state["meta"]["state_bytes"] = state_bytes
        updated = _serialized_size(state)
        if updated == state_bytes:
            break
        state_bytes = updated
    return state


def _serialized_size(state: dict) -> int:
    return len(json.dumps(state, separators=(",", ":"), sort_keys=True))


def _build_legal_actions(
    *,
    legal_actions: list[str],
    to_call: int,
    min_raise_to: int,
    max_raise_to: int,
) -> list[dict]:
    entries: list[dict] = []
    for action in legal_actions:
        if action in {"fold", "check"}:
            entries.append({"action": action})
        elif action == "call":
            call_amount = max(to_call, 0)
            entries.append(
                {
                    "action": action,
                    "min_amount": call_amount,
                    "max_amount": call_amount,
                }
            )
        elif action in {"bet", "raise"}:
            entries.append(
                {
                    "action": action,
                    "min_amount": min_raise_to,
                    "max_amount": max_raise_to,
                }
            )
    return entries


def _build_action_history(
    *,
    actions: list[ActionEvent],
    seat_to_player: dict[SeatId, str],
) -> list[dict]:
    history: list[dict] = []
    running_pot = 0
    for index, event in enumerate(actions):
        running_pot += max(event.amount, 0)
        history.append(
            {
                "index": index,
                "street": event.street,
                "player_id": seat_to_player[event.seat],
                "seat_id": event.seat,
                "action": event.action,
                "amount": event.amount,
                "pot_after": running_pot,
            }
        )
    return history
