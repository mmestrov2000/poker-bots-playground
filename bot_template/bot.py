BOT_PROTOCOL_VERSION = "2.0"


class PokerBot:
    """Starter bot — edit `act()` to implement your strategy."""

    def __init__(self):
        # Track how often each opponent has bet or raised, across the whole session.
        # Key: player_id (stable across hands).  Value: {"total": int, "raises": int}
        self.opponent_stats = {}
        self._seen_action_index = -1  # prevents double-counting history entries

    def act(self, state: dict) -> dict:
        """Called every time it is your turn. Return the action you want to take."""

        # ── My hand ──────────────────────────────────────────────────────────
        hero      = state["hero"]
        my_cards  = hero["hole_cards"]    # e.g. ["Ah", "Ks"]
        my_stack  = hero["stack"]         # chips remaining, in cents
        to_call   = hero["to_call"]       # amount needed to call
        min_raise = hero["min_raise_to"]  # minimum raise-to amount

        # ── The board ────────────────────────────────────────────────────────
        community = state["board"]["cards"]  # [] preflop, up to 5 cards by river
        pot       = state["board"]["pot"]
        street    = state["table"]["street"]  # "preflop", "flop", "turn", "river"

        # ── Other players ────────────────────────────────────────────────────
        for player in state["players"]:
            if player["is_hero"]:
                continue
            # player["player_id"] is stable — safe to use as a long-term tracking key
            # Other fields: player["stack"], player["bet"], player["folded"], player["all_in"]

        # ── Action history (new events only) ─────────────────────────────────
        # action_history grows throughout the hand; use "index" to skip already-seen events.
        for event in state["action_history"]:
            if event["index"] <= self._seen_action_index:
                continue
            self._seen_action_index = event["index"]

            pid    = event["player_id"]
            action = event["action"]  # "blind", "fold", "check", "call", "bet", "raise"
            amount = event["amount"]

            if pid != hero["player_id"]:  # skip your own actions
                stats = self.opponent_stats.setdefault(pid, {"total": 0, "raises": 0})
                stats["total"] += 1
                if action in ("bet", "raise"):
                    stats["raises"] += 1

        # ── Legal actions ─────────────────────────────────────────────────────
        # Only actions in this list are valid. Use the amounts provided — do not guess.
        # call  → min_amount == max_amount (fixed cost)
        # raise → min_amount is the minimum, max_amount is your stack
        legal = {entry["action"]: entry for entry in state["legal_actions"]}

        # ── Your strategy goes here ───────────────────────────────────────────
        if "check" in legal:
            return {"action": "check"}

        if "call" in legal and to_call <= pot // 4:
            return {"action": "call"}

        if "fold" in legal:
            return {"action": "fold"}

        # Fallback: take the first legal action with the minimum valid amount.
        first = next(iter(legal.values()))
        response = {"action": first["action"]}
        if "min_amount" in first:
            response["amount"] = first["min_amount"]
        return response
