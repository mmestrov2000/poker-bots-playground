# Bot Template

Your bot is a single Python file (`bot.py`) with one class and one method.

## Minimum viable bot

```python
BOT_PROTOCOL_VERSION = "2.0"

class PokerBot:
    def act(self, state: dict) -> dict:
        legal = {e["action"]: e for e in state["legal_actions"]}
        if "check" in legal:
            return {"action": "check"}
        if "call" in legal:
            return {"action": "call"}
        return {"action": "fold"}
```

That's a complete, working bot. The starter `bot.py` in this folder builds on it with opponent tracking.

## Package and upload

```bash
zip bot.zip bot.py
```

Go to **My Bots → Upload**, fill in a name and version, and upload `bot.zip`.

`bot.py` must be at the archive root (or inside exactly one top-level folder).

---

## The `state` dict

Every time it is your turn, `act(state)` is called. Here is what `state` contains:

```
state = {
  "table": {
    "street":      "preflop" | "flop" | "turn" | "river",
    "hand_id":     "hand-42",
    "button_seat": "1",
    "small_blind": 50,    # in cents
    "big_blind":   100
  },

  "hero": {
    "player_id":    "player-2",    # your stable ID across hands
    "hole_cards":   ["Ah", "Ks"],  # your two private cards
    "stack":        9800,          # your chips remaining (cents)
    "to_call":      100,           # cost to call
    "min_raise_to": 200,           # minimum raise total
    "max_raise_to": 9800           # maximum raise (your full stack)
  },

  "board": {
    "cards": ["Kd", "7c", "2h"],   # community cards (empty preflop)
    "pot":   300                   # current pot (cents)
  },

  "players": [                     # all seats, including yours
    {
      "player_id": "player-1",
      "stack":     9900,
      "bet":       100,
      "folded":    false,
      "all_in":    false,
      "is_hero":   false           # true only for your own entry
    },
    ...
  ],

  "legal_actions": [               # only these moves are valid right now
    {"action": "fold"},
    {"action": "call",  "min_amount": 100, "max_amount": 100},
    {"action": "raise", "min_amount": 200, "max_amount": 9800}
  ],

  "action_history": [              # every action in this hand so far
    {
      "index":     0,
      "street":    "preflop",
      "player_id": "player-1",
      "action":    "blind",
      "amount":    50,
      "pot_after": 50
    },
    ...
  ]
}
```

---

## Returning an action

Return a dict with `"action"` and, for `bet` or `raise`, an `"amount"`:

```python
return {"action": "fold"}
return {"action": "check"}
return {"action": "call"}
return {"action": "bet",   "amount": 200}
return {"action": "raise", "amount": 400}
```

Always use amounts from `legal_actions`. The call amount is fixed (`min_amount == max_amount`).
Raise amount must be between `min_amount` and `max_amount`.

---

## Tracking opponents across turns

`action_history` grows as the hand progresses. Use the `index` field to avoid processing the same event twice:

```python
def __init__(self):
    self._seen = -1

def act(self, state):
    for event in state["action_history"]:
        if event["index"] <= self._seen:
            continue
        self._seen = event["index"]
        # now process event["player_id"], event["action"], event["amount"]
```

`player_id` is stable for the entire session, so you can accumulate per-opponent stats across hands.

---

## Limits

| | |
|---|---|
| Decision timeout | 2 seconds |
| Memory | 256 MB |
| State payload | 64 KB |
| ZIP upload | 10 MB |
| Uncompressed archive | 2 MB |

---

## Test locally

From the repo root:

```bash
PYTHONPATH=. python - <<'PY'
import json
from pathlib import Path
from bot_template.bot import PokerBot

state = json.loads(Path("bot_template/fixtures/sample_v2_state.json").read_text())
bot = PokerBot()
print(bot.act(state))
PY
```
