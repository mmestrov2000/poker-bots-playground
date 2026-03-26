# Build a Poker Bot

This guide is written for event participants. If you know basic Python, you can follow these steps and end with a bot that is ready to upload.

If you want to build in JavaScript, C++, Go, or another language, also read [multi-language-bots.md](./multi-language-bots.md).

## The Short Version
- Your bot is a `.zip` file.
- Inside that zip, you need `bot.json` and `bot.py`.
- On each poker decision, the server runs `python bot.py`.
- Your bot reads the game state JSON from `stdin`.
- Your bot prints one action JSON object to `stdout`.
- Each decision is independent. Do not rely on Python variables staying alive between turns.

For this event, use Python. The platform runtime guarantees Python `3.12`.

The bot protocol itself is still language-agnostic:
- your program reads JSON from `stdin`
- your program writes JSON to `stdout`
- `bot.json` tells the server what command to run

If you want another language, the main rule is simple: the command in `bot.json` must be executable in the platform runtime. The multi-language guide linked above shows the patterns.

## Step 1: Copy the Starter Folder

Start from [`bot_template/`](../bot_template/).

Minimum files:

```text
my_bot/
  bot.json
  bot.py
```

`bot.json` tells the platform how to run your bot:

```json
{
  "command": ["python", "bot.py"],
  "protocol_version": "2.0"
}
```

Keep this exactly as shown unless you have a specific reason to change it.

If you are not using Python:
- JavaScript bots usually use `["node", "bot.js"]`
- compiled bots usually use `["./bot"]`
- details and examples are in [multi-language-bots.md](./multi-language-bots.md)

## Step 2: Understand What Your Bot Must Do

Your bot gets one JSON object on `stdin`. It must respond with one JSON object on `stdout`.

Example valid outputs:

```json
{"action": "fold"}
{"action": "check"}
{"action": "call"}
{"action": "bet", "amount": 200}
{"action": "raise", "amount": 400}
```

Rules:
- Only choose an action that appears in `legal_actions`.
- Only include `amount` for `bet` and `raise`.
- Keep `amount` within the provided bounds.
- Print only JSON to `stdout`.
- If you want debug logs, print them to `stderr`.

## Step 3: Write a Minimal Working Bot

Use this as your starting point:

```python
#!/usr/bin/env python3

import json
import sys


def choose_action(state: dict) -> dict:
    legal = {entry["action"]: entry for entry in state["legal_actions"]}

    if "check" in legal:
        return {"action": "check"}
    if "call" in legal:
        return {"action": "call"}
    return {"action": "fold"}


def main() -> int:
    state = json.load(sys.stdin)
    action = choose_action(state)
    json.dump(action, sys.stdout, separators=(",", ":"))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

This bot is simple, but it is valid and safe.

## Step 4: Learn the Input State

The most useful parts of the input JSON are:

- `hero`: your hole cards, current stack, amount to call, and raise bounds.
- `board`: community cards and current pot.
- `table`: street, hand id, blind levels, and button seat.
- `players`: all seats with stack, current bet, folded status, and whether the seat is you.
- `legal_actions`: the authoritative list of what you are allowed to do right now.
- `action_history`: the full ordered action log for the current hand.

Important idea:
- Your bot is stateless across calls.
- If you want to know what happened earlier in the hand, rebuild that information from `action_history`.
- Use the `index` field in `action_history` as the stable action order.

## Step 5: Make Better Decisions

Here are common things bots check:

- Preflop strength from `hero["hole_cards"]`
- Pot odds from `hero["to_call"]` and `board["pot"]`
- Position from `hero["seat_id"]` and `table["button_seat"]`
- Opponent aggression from `action_history`
- Stack pressure from `hero["stack"]`, `players`, and blind levels

The starter bot in [`bot_template/bot.py`](../bot_template/bot.py) already shows one useful pattern: counting opponent aggressive actions from `action_history`.

Readable examples are here:
- [`bot_template/examples/random_bot/bot.py`](../bot_template/examples/random_bot/bot.py)
- [`bot_template/examples/aggressive_bot/bot.py`](../bot_template/examples/aggressive_bot/bot.py)
- [`bot_template/examples/conservative_bot/bot.py`](../bot_template/examples/conservative_bot/bot.py)
- [`bot_template/examples/javascript_bot/bot.js`](../bot_template/examples/javascript_bot/bot.js)
- [`bot_template/examples/cpp_bot/bot.cpp`](../bot_template/examples/cpp_bot/bot.cpp)
- [`bot_template/examples/go_bot/bot.go`](../bot_template/examples/go_bot/bot.go)

## Step 6: Test Your Bot Locally

From the repo root:

```bash
python bot_template/bot.py < bot_template/fixtures/sample_v2_state.json
```

If you copied the template into `my_bot/`, test your own bot the same way:

```bash
python my_bot/bot.py < bot_template/fixtures/sample_v2_state.json
```

You should see one JSON action printed to the terminal.

## Step 7: Package Your Bot

Go into your bot folder and zip the files:

```bash
cd my_bot
zip -r my-bot.zip bot.json bot.py
```

If your bot uses extra files, include them too:

```bash
zip -r my-bot.zip bot.json bot.py lookup_table.json
```

If you create the zip with Finder, Explorer, or another GUI tool, that is also fine. Just make sure the zip contains `bot.json` and your bot files together. The platform accepts either:
- files at the zip root, or
- files inside exactly one top-level folder

Checklist before uploading:
- `bot.json` is inside the zip
- `bot.json` points to the correct command
- every referenced file is included in the zip
- your bot prints valid JSON to `stdout`
- your bot never prints logs to `stdout`

## Step 8: Upload Through the Website

1. Open the app.
2. Log in or register.
3. Go to `My Bots`.
4. Enter a bot name and version.
5. Upload your `.zip` file.
6. Create or open a table.
7. Seat your bot.
8. Start the match once at least two seats are filled.

## Step 9: Avoid the Most Common Mistakes

- Do not return an illegal action.
- Do not forget `amount` on `bet` or `raise`.
- Do not print explanations, logs, or extra text to `stdout`.
- Do not assume your Python object keeps state between decisions.
- Do not hardcode action sizes without checking `legal_actions`.
- Do not upload a zip that is missing `bot.json`.

## Step 10: Know the Runtime Limits

Current limits:

| Limit | Value |
|---|---|
| Decision timeout | 2 seconds |
| Memory | 256 MB |
| State payload | 64 KB |
| ZIP upload | 10 MB |
| Uncompressed archive | 2 MB |

Keep your bot simple, fast, and deterministic enough to respond comfortably within the time limit.

## Final Recommendation

If you are participating in the event and want the fastest path:

1. Copy `bot_template/`
2. Edit only `bot.py`
3. Keep `bot.json` unchanged
4. Test with `sample_v2_state.json`
5. Zip the folder
6. Upload it in `My Bots`

That path is the smoothest and the least likely to break during upload.

If you want to go beyond Python, use [multi-language-bots.md](./multi-language-bots.md) as your reference.
