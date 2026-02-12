from app.engine.game import ActionEvent, Card
from app.engine.hand_history import format_hand_history


def test_format_hand_history_contains_required_sections() -> None:
    rendered = format_hand_history(
        hand_id="42",
        winners=["1"],
        pot_size_cents=1250,
        seat_names={"1": "alpha.zip", "2": "beta.zip"},
        button="1",
        hole_cards={
            "1": [Card(rank=14, suit="s"), Card(rank=13, suit="h")],
            "2": [Card(rank=12, suit="d"), Card(rank=11, suit="c")],
        },
        board=[Card(rank=2, suit="s"), Card(rank=7, suit="h"), Card(rank=9, suit="d")],
        actions=[
            ActionEvent(seat="1", action="blind", amount=50, street="preflop"),
            ActionEvent(seat="2", action="blind", amount=100, street="preflop"),
            ActionEvent(seat="1", action="call", amount=50, street="preflop"),
        ],
        small_blind_cents=50,
        big_blind_cents=100,
    )

    assert "Hand #42" in rendered
    assert "*** HOLE CARDS ***" in rendered
    assert "*** SUMMARY ***" in rendered
    assert "Winner: Seat 1" in rendered
