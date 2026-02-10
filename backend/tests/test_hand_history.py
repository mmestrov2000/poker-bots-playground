from app.engine.game import ActionEvent, Card
from app.engine.hand_history import format_hand_history


def test_format_hand_history_contains_required_sections() -> None:
    rendered = format_hand_history(
        hand_id="42",
        winner="A",
        pot_size_cents=1250,
        seat_a_name="alpha.zip",
        seat_b_name="beta.zip",
        button="A",
        seat_a_cards=[Card(rank=14, suit="s"), Card(rank=13, suit="h")],
        seat_b_cards=[Card(rank=12, suit="d"), Card(rank=11, suit="c")],
        board=[Card(rank=2, suit="s"), Card(rank=7, suit="h"), Card(rank=9, suit="d")],
        actions=[
            ActionEvent(seat="A", action="blind", amount=50, street="preflop"),
            ActionEvent(seat="B", action="blind", amount=100, street="preflop"),
            ActionEvent(seat="A", action="call", amount=50, street="preflop"),
        ],
        small_blind_cents=50,
        big_blind_cents=100,
    )

    assert "Hand #42" in rendered
    assert "*** HOLE CARDS ***" in rendered
    assert "*** SUMMARY ***" in rendered
    assert "Winner: Seat A" in rendered
