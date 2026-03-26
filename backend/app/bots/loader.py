from __future__ import annotations

import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from app.bots.manifest import (
    is_archive_relative_command,
    normalize_command_relative_path,
    parse_manifest,
    select_manifest_member,
)
from app.bots.security import extract_archive_safely


class BotLoadError(RuntimeError):
    pass


@dataclass(frozen=True)
class PreparedBotArchive:
    extract_dir: Path
    working_dir: Path
    command: tuple[str, ...]


def save_upload(*, seat_id: str, filename: str, payload: bytes, uploads_dir: Path) -> Path:
    """Store uploaded bot archive in runtime uploads directory."""
    seat_dir = uploads_dir / seat_id
    seat_dir.mkdir(parents=True, exist_ok=True)
    destination = seat_dir / f"{uuid4().hex}_{filename}"
    destination.write_bytes(payload)
    return destination


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
        raise BotLoadError("bot.json must exist at zip root or one top-level folder") from exc
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
