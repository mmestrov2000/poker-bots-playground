from __future__ import annotations

import ast
import io
import zipfile

from app.bots.security import MAX_BOT_SOURCE_BYTES, validate_archive_infos


def validate_bot_archive(payload: bytes) -> tuple[bool, str | None]:
    if not payload:
        return False, "Upload payload is empty"

    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            is_valid, error_message = validate_archive_infos(archive.infolist())
            if not is_valid:
                return False, error_message

            bot_member, selection_error = select_bot_member(archive.namelist())
            if bot_member is None:
                return False, selection_error or "bot.py was not found in the zip"

            bot_info = archive.getinfo(bot_member)
            if bot_info.file_size > MAX_BOT_SOURCE_BYTES:
                return False, f"bot.py exceeds {MAX_BOT_SOURCE_BYTES} byte limit"

            with archive.open(bot_info) as bot_file:
                source = bot_file.read().decode("utf-8")
    except zipfile.BadZipFile:
        return False, "Upload is not a valid zip archive"
    except UnicodeDecodeError:
        return False, "bot.py must be valid UTF-8 text"
    except KeyError:
        return False, "bot.py was not found in the zip"

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False, "bot.py contains invalid Python syntax"

    has_bot_class = any(
        isinstance(node, ast.ClassDef) and node.name == "PokerBot" for node in tree.body
    )
    if not has_bot_class:
        return False, "bot.py must define a PokerBot class"

    return True, None


def select_bot_member(names: list[str]) -> tuple[str | None, str | None]:
    candidates: list[str] = []
    for name in names:
        if name.endswith("/"):
            continue
        parts = [p for p in name.split("/") if p]
        if parts and parts[-1] == "bot.py":
            candidates.append(name)

    if not candidates:
        return None, "bot.py must exist at zip root or one top-level folder"

    if "bot.py" in candidates:
        return "bot.py", None

    single_folder_candidates = [name for name in candidates if len([p for p in name.split("/") if p]) == 2]
    if len(single_folder_candidates) == 1:
        return single_folder_candidates[0], None
    if len(single_folder_candidates) > 1:
        return None, "Archive contains multiple bot.py candidates"

    return None, "bot.py must exist at zip root or one top-level folder"
