# Bot Starter Files

This folder contains the user-facing bot materials for the platform.

If you want a guided walkthrough, read [../docs/build-a-poker-bot.md](../docs/build-a-poker-bot.md) first.
If you want language-specific packaging examples, read [../docs/multi-language-bots.md](../docs/multi-language-bots.md).

## Folder Layout

- `examples/python_bot/`: the recommended starting point
- `examples/javascript_bot/`: Node.js example
- `examples/cpp_bot/`: C++ example that builds to `./bot`
- `examples/go_bot/`: Go example that builds to `./bot`
- `fixtures/sample_v2_state.json`: sample decision payload for local testing

## Recommended Starting Point

If you want the smoothest path, start from [`examples/python_bot/`](./examples/python_bot/).

That folder contains:
- `bot.json`
- `bot.py`

Its manifest is:

```json
{
  "command": ["python", "bot.py"],
  "protocol_version": "2.0"
}
```

Important:
- The contract is language-agnostic.
- The current platform runtime guarantees Python `3.12`.
- Other languages are possible when their interpreter or executable is available in the runtime.
- Bundled native executables keep their executable bit when the archive is extracted.

## Test locally

From the repo root:

```bash
python bot/examples/python_bot/bot.py < bot/fixtures/sample_v2_state.json
```

Or run it from inside the example folder:

```bash
cd bot/examples/python_bot
python bot.py < ../../fixtures/sample_v2_state.json
```

Then zip the files in your chosen example folder and upload them through **My Bots**.
