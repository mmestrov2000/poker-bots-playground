# Bot Template

MVP upload format expects a `.zip` archive containing `bot.py` at archive root or one top-level folder.
Optional `requirements.txt` is allowed at the same level as `bot.py`.

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
zip -r sample_bot.zip bot.py requirements.txt
```
