# Backend

## Run locally
```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
PYTHONPATH=. uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Run tests
```bash
cd backend
PYTHONPATH=. pytest -q
```
