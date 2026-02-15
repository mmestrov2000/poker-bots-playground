# Bot Template

Upload format expects a `.zip` archive containing `bot.py` at archive root.

## Required contract
`bot.py` must expose class `PokerBot` with method:

```python
class PokerBot:
    def act(self, state: dict) -> dict:
        ...
```

Returned dict shape:
- `action`: one of `fold`, `check`, `call`, `bet`, `raise`
- `amount`: integer when action requires amount

## Protocol version selection
Legacy protocol-v1 still works by default. To opt into protocol-v2, declare either:

```python
BOT_PROTOCOL_VERSION = "2.0"
```

or:

```python
class PokerBot:
    protocol_version = "2.0"
```

`bot_template/bot.py` includes both declarations for clarity.

## Protocol-v2 payload guide
The `state` payload for v2 contains:
- `protocol_version`: `"2.0"`
- `decision_id`: unique decision key
- `table`: `table_id`, `hand_id`, `street`, `button_seat`, blind values
- `hero`: your bot identity and decision bounds (`to_call`, `min_raise_to`, `max_raise_to`)
- `players`: all seats with stable `player_id` for per-opponent tracking
- `board`: board cards and current pot
- `legal_actions`: authoritative action list (`action`, optional `min_amount`/`max_amount`)
- `action_history`: full current-hand timeline with `index`, `player_id`, action, amount, `pot_after`
- `meta`: server timestamp and serialized state size in bytes

`legal_actions` is authoritative. Do not assume an action is legal if it is absent.

## Opponent tracking example
The starter bot demonstrates a simple parser strategy:
- track opponents by `players[*].player_id`
- process only unseen history entries using `action_history[*].index`
- accumulate per-opponent totals (actions, aggressive actions)

This is enough to implement features like:
- aggression-based calling/raising thresholds
- player-specific adjustments keyed by stable `player_id`

Use `bot_template/fixtures/sample_v2_state.json` to test parser changes quickly.

## Bot-local persistence expectations
Bots may use bot-managed local/external persistence, but keep these limits in mind:
- decision calls are time bounded (`2.0s` default), so persistence I/O in `act()` must be small and predictable
- incoming context payload size is capped (`64KiB` serialized state)
- bot local files/process memory are bot-owned only; do not rely on access to platform-private stores/services
- local disk persistence may be ephemeral depending on runtime lifecycle; design for cold starts and missing files

The starter bot includes optional helpers:
- `save_local_state(path)`
- `load_local_state(path)`

## Package example
```bash
cd bot_template
zip -r sample_bot.zip bot.py
```

## Quick smoke run
From repo root:

```bash
PYTHONPATH=. python - <<'PY'
import json
from pathlib import Path
from bot_template.bot import PokerBot

state = json.loads(Path("bot_template/fixtures/sample_v2_state.json").read_text())
bot = PokerBot()
print(bot.act(state))
print(bot.opponent_stats)
PY
```
