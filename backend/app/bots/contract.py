from typing import Protocol


class PokerBot(Protocol):
    def act(self, state: dict) -> dict:
        """Return {'action': 'fold|check|call|bet|raise', 'amount': int} when needed."""
