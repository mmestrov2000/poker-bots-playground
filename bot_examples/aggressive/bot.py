class PokerBot:
    """Simple aggressive example bot."""

    def act(self, state: dict) -> dict:
        legal_actions = state.get("legal_actions", [])
        min_bet = int(state.get("min_bet", 1))
        min_raise = int(state.get("min_raise", min_bet))

        if "raise" in legal_actions:
            return {"action": "raise", "amount": max(min_raise, min_bet * 3)}
        if "bet" in legal_actions:
            return {"action": "bet", "amount": max(min_bet * 2, 2)}
        if "call" in legal_actions:
            return {"action": "call"}
        if "check" in legal_actions:
            return {"action": "check"}
        return {"action": "fold"}
