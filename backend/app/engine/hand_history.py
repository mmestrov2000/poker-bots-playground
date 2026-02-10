from datetime import datetime, timezone


def format_hand_history(
    *,
    hand_id: str,
    winner: str,
    pot_size: float,
    seat_a_name: str,
    seat_b_name: str,
) -> str:
    """Return a readable poker-hand-history text blob for the MVP scaffold."""
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    return "\n".join(
        [
            f"Hand #{hand_id}",
            f"Date: {timestamp}",
            "Game: Hold'em No Limit ($0.50/$1.00)",
            f"Seat A: {seat_a_name}",
            f"Seat B: {seat_b_name}",
            "*** HOLE CARDS ***",
            "[MVP scaffold placeholder hand flow]",
            "*** SUMMARY ***",
            f"Total pot: {pot_size:.2f}",
            f"Winner: Seat {winner}",
        ]
    )
