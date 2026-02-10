from app.engine.hand_history import format_hand_history


def test_format_hand_history_contains_required_sections() -> None:
    rendered = format_hand_history(
        hand_id="42",
        winner="A",
        pot_size=12.5,
        seat_a_name="alpha.zip",
        seat_b_name="beta.zip",
    )

    assert "Hand #42" in rendered
    assert "*** HOLE CARDS ***" in rendered
    assert "*** SUMMARY ***" in rendered
    assert "Winner: Seat A" in rendered
