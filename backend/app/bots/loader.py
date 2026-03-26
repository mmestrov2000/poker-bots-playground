from __future__ import annotations

import ast
import importlib.util
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from uuid import uuid4

from app.bots.manifest import (
    is_archive_relative_command,
    normalize_command_relative_path,
    parse_manifest,
    select_manifest_member,
)
from app.bots.protocol import (
    extract_declared_protocol_from_ast,
    normalize_protocol_value,
    select_runtime_protocol,
)
from app.bots.security import extract_archive_safely
from app.bots.validator import select_bot_member


class BotLoadError(RuntimeError):
    pass


@dataclass(frozen=True)
class PreparedBotArchive:
    extract_dir: Path
    working_dir: Path
    command: tuple[str, ...]
    protocol_version: str


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
    _extract_archive(zip_path=zip_path, extract_dir=extract_dir)

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
    setattr(bot_instance, "_ppg_extract_dir", str(extract_dir))

    return bot_instance


def prepare_bot_archive(zip_path: Path) -> PreparedBotArchive:
    if not zip_path.exists():
        raise BotLoadError("bot archive not found")
    if not zipfile.is_zipfile(zip_path):
        raise BotLoadError("bot archive is not a valid zip")

    extract_dir = zip_path.parent / f"unpacked_{uuid4().hex}"
    extract_dir.mkdir(parents=True, exist_ok=True)
    try:
        _extract_archive(zip_path=zip_path, extract_dir=extract_dir)
        with zipfile.ZipFile(zip_path, "r") as archive:
            manifest_member, manifest_error = select_manifest_member(archive.namelist())
            if manifest_member is None:
                raise BotLoadError(manifest_error or "bot.json must exist at zip root or one top-level folder")
            with archive.open(manifest_member) as manifest_file:
                manifest, error = parse_manifest(
                    raw_manifest=manifest_file.read(),
                    manifest_member=manifest_member,
                    archive_names=archive.namelist(),
                )
    except KeyError as exc:
        shutil.rmtree(extract_dir, ignore_errors=True)
        raise BotLoadError("bot.json was not found in the zip") from exc
    except UnicodeDecodeError as exc:
        shutil.rmtree(extract_dir, ignore_errors=True)
        raise BotLoadError("bot.json must be valid UTF-8 text") from exc
    except zipfile.BadZipFile as exc:
        shutil.rmtree(extract_dir, ignore_errors=True)
        raise BotLoadError("bot archive is not a valid zip") from exc
    except Exception:
        shutil.rmtree(extract_dir, ignore_errors=True)
        raise

    if manifest is None:
        shutil.rmtree(extract_dir, ignore_errors=True)
        raise BotLoadError(error or "Invalid bot manifest")

    working_dir = extract_dir if not manifest.root_dir.parts else extract_dir.joinpath(*manifest.root_dir.parts)
    try:
        command = _materialize_command(command=manifest.command, working_dir=working_dir)
    except Exception:
        shutil.rmtree(extract_dir, ignore_errors=True)
        raise
    return PreparedBotArchive(
        extract_dir=extract_dir,
        working_dir=working_dir,
        command=command,
        protocol_version=manifest.protocol_version,
    )


def has_manifest_contract(zip_path: Path) -> bool:
    if not zip_path.exists():
        raise BotLoadError("bot archive not found")
    if not zipfile.is_zipfile(zip_path):
        raise BotLoadError("bot archive is not a valid zip")

    try:
        with zipfile.ZipFile(zip_path, "r") as archive:
            manifest_member, manifest_error = select_manifest_member(archive.namelist())
    except zipfile.BadZipFile as exc:
        raise BotLoadError("bot archive is not a valid zip") from exc

    if manifest_error:
        raise BotLoadError(manifest_error)
    return manifest_member is not None


def resolve_bot_protocol_from_zip(zip_path: Path) -> str:
    if not zip_path.exists():
        raise BotLoadError("bot archive not found")
    if not zipfile.is_zipfile(zip_path):
        raise BotLoadError("bot archive is not a valid zip")

    try:
        with zipfile.ZipFile(zip_path, "r") as archive:
            manifest_member, manifest_error = select_manifest_member(archive.namelist())
            if manifest_member is not None:
                with archive.open(manifest_member) as manifest_file:
                    manifest, error = parse_manifest(
                        raw_manifest=manifest_file.read(),
                        manifest_member=manifest_member,
                        archive_names=archive.namelist(),
                    )
                if manifest is None:
                    raise BotLoadError(error or "Invalid bot manifest")
                return manifest.protocol_version
            if manifest_error:
                raise BotLoadError(manifest_error)

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


def _extract_archive(*, zip_path: Path, extract_dir: Path) -> None:
    with zipfile.ZipFile(zip_path, "r") as archive:
        try:
            extract_archive_safely(archive, extract_dir)
        except ValueError as exc:
            raise BotLoadError(str(exc)) from exc


def _materialize_command(*, command: tuple[str, ...], working_dir: Path) -> tuple[str, ...]:
    executable = command[0]
    if not is_archive_relative_command(executable):
        return command

    normalized, error = normalize_command_relative_path(executable)
    if normalized is None:
        raise BotLoadError(error or "Invalid bot command")

    resolved = working_dir.joinpath(*normalized.parts)
    if not resolved.is_file():
        raise BotLoadError(f"bot.json command entry '{executable}' was not found in the archive")
    return (str(resolved), *command[1:])


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
