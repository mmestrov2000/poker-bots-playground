from __future__ import annotations

import ast
import json
from datetime import datetime, timezone
from typing import Any

SeatId = str
Card = Any
ActionEvent = Any

LEGACY_PROTOCOL_VERSION = "1.0"
PROTOCOL_V2 = "2.0"
SUPPORTED_DECLARED_PROTOCOLS = {PROTOCOL_V2}


def normalize_protocol_value(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return str(value)
    normalized = value.strip()
    return normalized or None


def resolve_declared_protocol(
    *,
    module_protocol: str | None,
    class_protocol: str | None,
) -> str | None:
    return module_protocol if module_protocol is not None else class_protocol


def select_runtime_protocol(
    *,
    module_protocol: str | None,
    class_protocol: str | None,
) -> str:
    declared = resolve_declared_protocol(
        module_protocol=normalize_protocol_value(module_protocol),
        class_protocol=normalize_protocol_value(class_protocol),
    )
    if declared == PROTOCOL_V2:
        return PROTOCOL_V2
    return LEGACY_PROTOCOL_VERSION


def resolve_bot_protocol(bot: object) -> str:
    module_protocol = normalize_protocol_value(getattr(bot, "_ppg_module_protocol_version", None))
    class_protocol = normalize_protocol_value(getattr(bot, "_ppg_class_protocol_version", None))
    if class_protocol is None:
        class_protocol = normalize_protocol_value(getattr(bot.__class__, "protocol_version", None))
    return select_runtime_protocol(module_protocol=module_protocol, class_protocol=class_protocol)


def extract_declared_protocol_from_ast(tree: ast.AST) -> tuple[str | None, str | None, str | None]:
    module_protocol, module_error = _extract_module_protocol(tree)
    if module_error:
        return None, None, module_error

    class_protocol, class_error = _extract_class_protocol(tree)
    if class_error:
        return None, None, class_error

    declared = resolve_declared_protocol(
        module_protocol=module_protocol,
        class_protocol=class_protocol,
    )
    if declared is None:
        return module_protocol, class_protocol, None
    if declared not in SUPPORTED_DECLARED_PROTOCOLS:
        return (
            module_protocol,
            class_protocol,
            f"Unsupported protocol version '{declared}'. Supported declared versions: {', '.join(sorted(SUPPORTED_DECLARED_PROTOCOLS))}",
        )
    return module_protocol, class_protocol, None


def _extract_module_protocol(tree: ast.AST) -> tuple[str | None, str | None]:
    module_value: str | None = None
    if not isinstance(tree, ast.Module):
        return None, None
    for node in tree.body:
        if isinstance(node, ast.Assign):
            if not any(isinstance(target, ast.Name) and target.id == "BOT_PROTOCOL_VERSION" for target in node.targets):
                continue
            value, error = _literal_string(node.value, "BOT_PROTOCOL_VERSION")
            if error:
                return None, error
            module_value = value
        elif isinstance(node, ast.AnnAssign):
            if not (isinstance(node.target, ast.Name) and node.target.id == "BOT_PROTOCOL_VERSION"):
                continue
            value, error = _literal_string(node.value, "BOT_PROTOCOL_VERSION")
            if error:
                return None, error
            module_value = value
    return module_value, None


def _extract_class_protocol(tree: ast.AST) -> tuple[str | None, str | None]:
    if not isinstance(tree, ast.Module):
        return None, None
    for node in tree.body:
        if not isinstance(node, ast.ClassDef) or node.name != "PokerBot":
            continue
        class_value: str | None = None
        for class_node in node.body:
            if isinstance(class_node, ast.Assign):
                if not any(isinstance(target, ast.Name) and target.id == "protocol_version" for target in class_node.targets):
                    continue
                value, error = _literal_string(class_node.value, "PokerBot.protocol_version")
                if error:
                    return None, error
                class_value = value
            elif isinstance(class_node, ast.AnnAssign):
                if not (isinstance(class_node.target, ast.Name) and class_node.target.id == "protocol_version"):
                    continue
                value, error = _literal_string(class_node.value, "PokerBot.protocol_version")
                if error:
                    return None, error
                class_value = value
        return class_value, None
    return None, None


def _literal_string(value_node: ast.expr | None, label: str) -> tuple[str | None, str | None]:
    if value_node is None:
        return None, f"{label} must be a string literal"
    if not isinstance(value_node, ast.Constant) or not isinstance(value_node.value, str):
        return None, f"{label} must be a string literal"
    value = normalize_protocol_value(value_node.value)
    if value is None:
        return None, f"{label} must be a non-empty string"
    return value, None


def build_decision_state(
    *,
    protocol_version: str,
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
    if protocol_version != PROTOCOL_V2:
        return build_legacy_state(
            seat=seat,
            street=street,
            hole_cards=hole_cards,
            board=board,
            pot=pot,
            stack=stack,
            to_call=to_call,
            min_raise_to=min_raise_to,
            legal_actions=legal_actions,
            seat_name=seat_name,
            seats=seats,
            seat_names=seat_names,
            stacks=stacks,
            bets=bets,
            folded=folded,
            button=button,
            small_blind=small_blind,
            big_blind=big_blind,
        )

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


def build_legacy_state(
    *,
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
) -> dict:
    return {
        "seat": seat,
        "seat_name": seat_name,
        "street": street,
        "hole_cards": [str(card) for card in hole_cards],
        "board": [str(card) for card in board],
        "pot": pot,
        "stack": stack,
        "to_call": to_call,
        "min_raise_to": min_raise_to,
        "legal_actions": legal_actions,
        "players": [
            {
                "seat": seat_id,
                "name": seat_names[seat_id],
                "stack": stacks[seat_id],
                "bet": bets[seat_id],
                "folded": seat_id in folded,
                "all_in": stacks[seat_id] == 0,
            }
            for seat_id in seats
        ],
        "button": button,
        "small_blind": small_blind,
        "big_blind": big_blind,
    }
