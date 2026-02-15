from __future__ import annotations

import ast
import importlib.util
import zipfile
from pathlib import Path
from types import ModuleType
from uuid import uuid4

from app.bots.protocol import (
    extract_declared_protocol_from_ast,
    normalize_protocol_value,
    select_runtime_protocol,
)
from app.bots.security import extract_archive_safely
from app.bots.validator import select_bot_member


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
        try:
            extract_archive_safely(archive, extract_dir)
        except ValueError as exc:
            raise BotLoadError(str(exc)) from exc

    bot_file = _resolve_bot_entrypoint(extract_dir)
    if bot_file is None:
        raise BotLoadError("bot.py must exist at zip root or one top-level folder")

    module = _load_module(bot_file)
    bot_cls = getattr(module, "PokerBot", None)
    if bot_cls is None:
        raise BotLoadError("PokerBot class missing")

    bot_instance = bot_cls()
    if not hasattr(bot_instance, "act"):
        raise BotLoadError("PokerBot.act missing")
    setattr(
        bot_instance,
        "_ppg_module_protocol_version",
        normalize_protocol_value(getattr(module, "BOT_PROTOCOL_VERSION", None)),
    )
    setattr(
        bot_instance,
        "_ppg_class_protocol_version",
        normalize_protocol_value(getattr(bot_cls, "protocol_version", None)),
    )

    return bot_instance


def resolve_bot_protocol_from_zip(zip_path: Path) -> str:
    if not zip_path.exists():
        raise BotLoadError("bot archive not found")
    if not zipfile.is_zipfile(zip_path):
        raise BotLoadError("bot archive is not a valid zip")

    try:
        with zipfile.ZipFile(zip_path, "r") as archive:
            bot_member, selection_error = select_bot_member(archive.namelist())
            if bot_member is None:
                raise BotLoadError(selection_error or "bot.py must exist at zip root or one top-level folder")
            with archive.open(bot_member) as bot_file:
                source = bot_file.read().decode("utf-8")
    except KeyError as exc:
        raise BotLoadError("bot.py was not found in the zip") from exc
    except UnicodeDecodeError as exc:
        raise BotLoadError("bot.py must be valid UTF-8 text") from exc
    except zipfile.BadZipFile as exc:
        raise BotLoadError("bot archive is not a valid zip") from exc

    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise BotLoadError("bot.py contains invalid Python syntax") from exc

    module_protocol, class_protocol, protocol_error = extract_declared_protocol_from_ast(tree)
    if protocol_error:
        raise BotLoadError(protocol_error)
    return select_runtime_protocol(
        module_protocol=module_protocol,
        class_protocol=class_protocol,
    )


def _load_module(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"bot_{uuid4().hex}", path)
    if spec is None or spec.loader is None:
        raise BotLoadError("unable to load bot module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _resolve_bot_entrypoint(extract_dir: Path) -> Path | None:
    root_bot = extract_dir / "bot.py"
    if root_bot.exists():
        return root_bot

    nested_bots = [path for path in extract_dir.glob("*/bot.py") if path.is_file()]
    if len(nested_bots) == 1:
        return nested_bots[0]
    if len(nested_bots) > 1:
        raise BotLoadError("Archive contains multiple bot.py candidates")
    return None
