# Bot Template

MVP upload format expects a `.zip` archive containing `bot.py` at archive root.

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

## Package example
```bash
cd bot_template
zip -r sample_bot.zip bot.py
```
