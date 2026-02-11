# Bot Examples

These examples follow the same contract as `bot_template/bot.py` and can be uploaded to seats `A` and `B`.

## Included bots
- `aggressive/bot.py`: prioritizes `raise` and `bet` when available.
- `conservative/bot.py`: prefers `check`, folds often, and only calls small amounts.

## Package bots for upload
From repository root:

```bash
cd bot_examples/aggressive && zip -r ../aggressive_bot.zip bot.py
cd ../conservative && zip -r ../conservative_bot.zip bot.py
```

This creates:
- `bot_examples/aggressive_bot.zip`
- `bot_examples/conservative_bot.zip`

Both archives have `bot.py` at zip root, which is required by the backend validator.

## Upload via UI
1. Start the app (`docker compose up --build` or local `uvicorn` flow from `README.md`).
2. Open `http://localhost:8000`.
3. Upload `bot_examples/aggressive_bot.zip` into seat `A`.
4. Upload `bot_examples/conservative_bot.zip` into seat `B`.
5. Confirm both seats show ready/running state and hands begin appearing.

## Upload via API
```bash
curl -X POST "http://localhost:8000/api/v1/seats/A/bot" \
  -F "bot_file=@bot_examples/aggressive_bot.zip"

curl -X POST "http://localhost:8000/api/v1/seats/B/bot" \
  -F "bot_file=@bot_examples/conservative_bot.zip"
```

Useful checks:

```bash
curl "http://localhost:8000/api/v1/match"
curl "http://localhost:8000/api/v1/hands?limit=5"
curl "http://localhost:8000/api/v1/hands/<hand_id>"
```
