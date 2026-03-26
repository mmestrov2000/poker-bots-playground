# Bot Template

Your bot is a ZIP package that declares how to run itself and communicates over stdin/stdout JSON.

## Package layout

This folder contains the minimum working package:

- `bot.json` declares the command the server should run
- `bot.py` reads one decision state JSON object from stdin and writes one action JSON object to stdout

`bot.json`:

```json
{
  "command": ["python", "bot.py"],
  "protocol_version": "2.0"
}
```

The command is executed from the package root. Use a command array, not a shell string.

## Minimum viable bot

```python
import json
import sys


def choose_action(state: dict) -> dict:
    legal = {entry["action"]: entry for entry in state["legal_actions"]}
    if "check" in legal:
        return {"action": "check"}
    if "call" in legal:
        return {"action": "call"}
    return {"action": "fold"}


state = json.load(sys.stdin)
json.dump(choose_action(state), sys.stdout)
```

That is a complete working bot. The starter `bot.py` in this folder adds simple opponent-history parsing without relying on in-process state.

## Package and upload

```bash
zip bot.zip bot.json bot.py
```

Go to **My Bots → Upload**, fill in a name and version, and upload `bot.zip`.

`bot.json` must exist at the archive root or inside exactly one top-level folder. Relative paths in `command[0]` are resolved from the folder that contains `bot.json`.

## The state JSON

Every time it is your turn, the server runs your command and sends one JSON object on stdin.

```json
{
  "protocol_version": "2.0",
  "decision_id": "table-1:hand-42:turn:2:7",
  "table": {
    "table_id": "table-1",
    "hand_id": "hand-42",
    "street": "preflop",
    "button_seat": "1",
    "small_blind": 50,
    "big_blind": 100
  },
  "hero": {
    "player_id": "player-2",
    "seat_id": "2",
    "name": "beta",
    "hole_cards": ["Ah", "Ks"],
    "stack": 9800,
    "bet": 100,
    "to_call": 100,
    "min_raise_to": 200,
    "max_raise_to": 9800
  },
  "board": {
    "cards": ["Kd", "7c", "2h"],
    "pot": 300
  },
  "players": [
    {
      "player_id": "player-1",
      "seat_id": "1",
      "name": "alpha",
      "stack": 9900,
      "bet": 100,
      "folded": false,
      "all_in": false,
      "is_hero": false
    }
  ],
  "legal_actions": [
    {"action": "fold"},
    {"action": "call", "min_amount": 100, "max_amount": 100},
    {"action": "raise", "min_amount": 200, "max_amount": 9800}
  ],
  "action_history": [
    {
      "index": 0,
      "street": "preflop",
      "player_id": "player-1",
      "seat_id": "1",
      "action": "blind",
      "amount": 50,
      "pot_after": 50
    }
  ],
  "meta": {
    "server_time": "2026-03-26T10:00:00+00:00",
    "state_bytes": 512
  }
}
```

Because each decision is independent, use `action_history` to reconstruct everything you need for the current hand.

## Returning an action

Write exactly one JSON object to stdout:

```json
{"action": "fold"}
{"action": "check"}
{"action": "call"}
{"action": "bet", "amount": 200}
{"action": "raise", "amount": 400}
```

Use only actions from `legal_actions`. For `bet` and `raise`, `amount` must stay within the provided bounds.

Send logs to stderr if you need them. Stdout must contain only the action JSON.

## Limits

| | |
|---|---|
| Decision timeout | 2 seconds |
| Memory | 256 MB |
| State payload | 64 KB |
| ZIP upload | 10 MB |
| Uncompressed archive | 2 MB |

## Test locally

From the repo root:

```bash
python bot_template/bot.py < bot_template/fixtures/sample_v2_state.json
```

Or test the packaged command exactly as the server will run it:

```bash
cd bot_template
python bot.py < fixtures/sample_v2_state.json
```
