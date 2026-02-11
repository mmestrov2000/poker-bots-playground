class PokerBot:
    """Simple conservative example bot."""

    def act(self, state: dict) -> dict:
        legal_actions = state.get("legal_actions", [])
        to_call = int(state.get("to_call", 0))

        if "check" in legal_actions:
            return {"action": "check"}
        if "call" in legal_actions and to_call <= 2:
            return {"action": "call"}
        if "fold" in legal_actions:
            return {"action": "fold"}
        if "call" in legal_actions:
            return {"action": "call"}
        if "bet" in legal_actions:
            return {"action": "bet", "amount": int(state.get("min_bet", 1))}
        return {"action": "check"}
