from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any

from app.bots.protocol import PROTOCOL_V2, normalize_protocol_value


BOT_MANIFEST_NAME = "bot.json"
SUPPORTED_MANIFEST_PROTOCOLS = {PROTOCOL_V2}


@dataclass(frozen=True)
class BotManifest:
    command: tuple[str, ...]
    protocol_version: str
    member_path: str
    root_dir: PurePosixPath


def select_manifest_member(names: list[str]) -> tuple[str | None, str | None]:
    candidates = _select_named_members(names, BOT_MANIFEST_NAME)
    if not candidates:
        return None, f"{BOT_MANIFEST_NAME} must exist at zip root or one top-level folder"
    if BOT_MANIFEST_NAME in candidates:
        return BOT_MANIFEST_NAME, None

    single_folder_candidates = [name for name in candidates if len([p for p in name.split("/") if p]) == 2]
    if len(single_folder_candidates) == 1:
        return single_folder_candidates[0], None
    if len(single_folder_candidates) > 1:
        return None, f"Archive contains multiple {BOT_MANIFEST_NAME} candidates"

    return None, f"{BOT_MANIFEST_NAME} must exist at zip root or one top-level folder"


def parse_manifest(
    *,
    raw_manifest: bytes,
    manifest_member: str,
    archive_names: list[str],
    path_env: str | None = None,
) -> tuple[BotManifest | None, str | None]:
    try:
        payload = json.loads(raw_manifest.decode("utf-8"))
    except UnicodeDecodeError:
        return None, f"{BOT_MANIFEST_NAME} must be valid UTF-8 text"
    except json.JSONDecodeError:
        return None, f"{BOT_MANIFEST_NAME} must be valid JSON"

    if not isinstance(payload, dict):
        return None, f"{BOT_MANIFEST_NAME} must contain a JSON object"

    command = payload.get("command")
    if not isinstance(command, list) or not command:
        return None, f"{BOT_MANIFEST_NAME} command must be a non-empty array of strings"
    if not all(isinstance(entry, str) and entry.strip() for entry in command):
        return None, f"{BOT_MANIFEST_NAME} command must be a non-empty array of strings"
    normalized_command = tuple(entry.strip() for entry in command)

    protocol_value = normalize_protocol_value(payload.get("protocol_version")) or PROTOCOL_V2
    if protocol_value not in SUPPORTED_MANIFEST_PROTOCOLS:
        return (
            None,
            f"Unsupported protocol version '{protocol_value}'. Supported declared versions: {', '.join(sorted(SUPPORTED_MANIFEST_PROTOCOLS))}",
        )

    manifest_path = PurePosixPath(manifest_member)
    root_dir = PurePosixPath(*manifest_path.parts[:-1]) if len(manifest_path.parts) > 1 else PurePosixPath()
    command_error = validate_manifest_command(
        command=normalized_command,
        archive_names=archive_names,
        root_dir=root_dir,
        path_env=path_env,
    )
    if command_error:
        return None, command_error

    return BotManifest(
        command=normalized_command,
        protocol_version=protocol_value,
        member_path=manifest_member,
        root_dir=root_dir,
    ), None


def validate_manifest_command(
    *,
    command: tuple[str, ...],
    archive_names: list[str],
    root_dir: PurePosixPath,
    path_env: str | None = None,
) -> str | None:
    executable = command[0]
    if os.path.isabs(executable):
        return f"{BOT_MANIFEST_NAME} command[0] must not be an absolute path"

    if _is_archive_relative_command(executable):
        normalized, error = normalize_command_relative_path(executable)
        if error:
            return error
        target = _prefix_with_root(normalized, root_dir)
        if target.as_posix() not in set(_non_directory_members(archive_names)):
            return f"{BOT_MANIFEST_NAME} command entry '{executable}' was not found in the archive"
        return None

    if shutil.which(executable, path=path_env or os.environ.get("PATH")) is None:
        return f"{BOT_MANIFEST_NAME} command executable '{executable}' is not available in the runtime"
    return None


def normalize_command_relative_path(path_value: str) -> tuple[PurePosixPath | None, str | None]:
    normalized_value = path_value.strip()
    while normalized_value.startswith("./"):
        normalized_value = normalized_value[2:]
    if not normalized_value:
        return None, f"{BOT_MANIFEST_NAME} command entry must not be empty"
    if normalized_value.startswith("/"):
        return None, f"{BOT_MANIFEST_NAME} command entry must not be an absolute path"
    if "\\" in normalized_value:
        return None, f"{BOT_MANIFEST_NAME} command entry uses unsupported path separators"

    normalized = PurePosixPath(normalized_value)
    if any(part in {"", ".", ".."} for part in normalized.parts):
        return None, f"{BOT_MANIFEST_NAME} command entry contains unsafe path segments"
    return normalized, None


def is_archive_relative_command(executable: str) -> bool:
    return _is_archive_relative_command(executable)


def _is_archive_relative_command(executable: str) -> bool:
    return executable.startswith("./") or "/" in executable or "\\" in executable


def _select_named_members(names: list[str], filename: str) -> list[str]:
    candidates: list[str] = []
    for name in names:
        if name.endswith("/"):
            continue
        parts = [p for p in name.split("/") if p]
        if parts and parts[-1] == filename:
            candidates.append(name)
    return candidates


def _prefix_with_root(path: PurePosixPath, root_dir: PurePosixPath) -> PurePosixPath:
    if not root_dir.parts:
        return path
    return PurePosixPath(*root_dir.parts, *path.parts)


def _non_directory_members(names: list[str]) -> list[str]:
    return [name for name in names if not name.endswith("/")]
