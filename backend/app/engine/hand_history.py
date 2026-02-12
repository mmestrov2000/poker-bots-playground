from __future__ import annotations

from datetime import datetime, timezone

from app.engine.game import ActionEvent, Card, SeatId, order_seats


def format_hand_history(
    *,
    hand_id: str,
    winners: list[SeatId],
    pot_size_cents: int,
    seat_names: dict[SeatId, str],
    button: SeatId,
    hole_cards: dict[SeatId, list[Card]],
    board: list[Card],
    actions: list[ActionEvent],
    small_blind_cents: int,
    big_blind_cents: int,
) -> str:
    """Return a readable poker-hand-history text blob for the MVP engine."""
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    lines: list[str] = []

    lines.append(f"Hand #{hand_id}")
    lines.append(f"Date: {timestamp}")
    lines.append("Game: Hold'em No Limit ($0.50/$1.00)")
    ordered_seats = order_seats(seat_names.keys())
    for seat in ordered_seats:
        lines.append(f"Seat {seat}: {seat_names[seat]}")
    lines.append(f"Button: Seat {button}")
    lines.append("*** HOLE CARDS ***")
    for seat in ordered_seats:
        cards = " ".join(str(card) for card in hole_cards[seat])
        lines.append(f"Seat {seat}: [{cards}]")

    by_street = _group_actions(actions)
    _append_street(lines, "PREFLOP", by_street.get("preflop", []))
    if board:
        flop = board[:3]
        _append_street(lines, f"FLOP [{_cards_str(flop)}]", by_street.get("flop", []))
    if len(board) >= 4:
        turn = board[3:4]
        _append_street(
            lines,
            f"TURN [{_cards_str(board[:3])}] [{_cards_str(turn)}]",
            by_street.get("turn", []),
        )
    if len(board) == 5:
        river = board[4:5]
        _append_street(
            lines,
            f"RIVER [{_cards_str(board[:4])}] [{_cards_str(river)}]",
            by_street.get("river", []),
        )

    lines.append("*** SUMMARY ***")
    lines.append(f"Total pot: ${pot_size_cents / 100:.2f}")
    winner_label = ", ".join(f"Seat {seat}" for seat in winners)
    if len(winners) == 1:
        lines.append(f"Winner: {winner_label}")
    else:
        lines.append(f"Winners: {winner_label}")
    lines.append(f"Board: [{_cards_str(board)}]")
    lines.append(f"Blinds: ${small_blind_cents / 100:.2f}/${big_blind_cents / 100:.2f}")

    return "\n".join(lines)


def _group_actions(actions: list[ActionEvent]) -> dict[str, list[ActionEvent]]:
    grouped: dict[str, list[ActionEvent]] = {}
    for action in actions:
        grouped.setdefault(action.street, []).append(action)
    return grouped


def _append_street(lines: list[str], label: str, actions: list[ActionEvent]) -> None:
    lines.append(f"*** {label} ***")
    for action in actions:
        if action.action == "blind":
            lines.append(f"Seat {action.seat} posts blind ${action.amount / 100:.2f}")
        elif action.action in {"call", "bet", "raise"}:
            lines.append(
                f"Seat {action.seat} {action.action}s ${action.amount / 100:.2f}"
            )
        else:
            lines.append(f"Seat {action.seat} {action.action}")


def _cards_str(cards: list[Card]) -> str:
    return " ".join(str(card) for card in cards)
