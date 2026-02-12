from __future__ import annotations

import hashlib
import json
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path


def derive_bot_id(filename: str, payload: bytes) -> str:
    stem = Path(filename).stem.lower()
    base = re.sub(r"[^a-z0-9]+", "_", stem).strip("_") or "bot"
    digest = hashlib.sha256(payload).hexdigest()[:10]
    return f"{base}_{digest}"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _generate_password() -> str:
    return secrets.token_urlsafe(18)


class BotRegistry:
    def __init__(self, path: Path | None = None) -> None:
        if path is None:
            repo_root = Path(__file__).resolve().parents[3]
            path = repo_root / "runtime" / "bots" / "registry.json"
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_text(json.dumps({"bots": {}}, indent=2), encoding="utf-8")

    def _load(self) -> dict:
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _save(self, data: dict) -> None:
        self.path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")

    def get(self, bot_id: str) -> dict | None:
        data = self._load()
        return data.get("bots", {}).get(bot_id)

    def ensure_entry(
        self,
        *,
        bot_id: str,
        bot_name: str,
        schema: str,
        db_user: str,
    ) -> dict:
        data = self._load()
        bots = data.setdefault("bots", {})
        now = _utc_now()
        entry = bots.get(bot_id)
        if entry:
            entry["bot_name"] = bot_name
            entry["schema"] = schema
            entry["db_user"] = db_user
            entry["updated_at"] = now
        else:
            entry = {
                "bot_id": bot_id,
                "bot_name": bot_name,
                "schema": schema,
                "db_user": db_user,
                "db_password": _generate_password(),
                "created_at": now,
                "updated_at": now,
            }
        bots[bot_id] = entry
        self._save(data)
        return entry
