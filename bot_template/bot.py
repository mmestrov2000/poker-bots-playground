import random


class PokerBot:
    """Starter bot contract for uploads in the MVP playground."""

    def act(self, state: dict) -> dict:
        legal_actions = state.get("legal_actions", ["check"])

        if "check" in legal_actions:
            return {"action": "check"}
        if "call" in legal_actions:
            return {"action": "call"}
        if "fold" in legal_actions:
            return {"action": "fold"}

        action = random.choice(legal_actions)
        return {"action": action, "amount": state.get("min_bet", 1)}
