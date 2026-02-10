from __future__ import annotations

import importlib.util
import zipfile
from pathlib import Path
from types import ModuleType
from uuid import uuid4


class BotLoadError(RuntimeError):
    pass


def save_upload(*, seat_id: str, filename: str, payload: bytes, uploads_dir: Path) -> Path:
    """Store uploaded bot archive in runtime uploads directory."""
    seat_dir = uploads_dir / seat_id
    seat_dir.mkdir(parents=True, exist_ok=True)
    destination = seat_dir / f"{uuid4().hex}_{filename}"
    destination.write_bytes(payload)
    return destination


def load_bot_from_zip(zip_path: Path) -> object:
    if not zip_path.exists():
        raise BotLoadError("bot archive not found")
    if not zipfile.is_zipfile(zip_path):
        raise BotLoadError("bot archive is not a valid zip")

    extract_dir = zip_path.parent / f"unpacked_{uuid4().hex}"
    extract_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as archive:
        archive.extractall(extract_dir)

    bot_file = extract_dir / "bot.py"
    if not bot_file.exists():
        raise BotLoadError("bot.py entrypoint missing")

    module = _load_module(bot_file)
    bot_cls = getattr(module, "PokerBot", None)
    if bot_cls is None:
        raise BotLoadError("PokerBot class missing")

    bot_instance = bot_cls()
    if not hasattr(bot_instance, "act"):
        raise BotLoadError("PokerBot.act missing")

    return bot_instance


def _load_module(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"bot_{uuid4().hex}", path)
    if spec is None or spec.loader is None:
        raise BotLoadError("unable to load bot module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
