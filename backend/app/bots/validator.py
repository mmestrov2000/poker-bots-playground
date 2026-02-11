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

            names = set(archive.namelist())
            if "bot.py" not in names:
                return False, "bot.py must be at the root of the zip"

            bot_info = archive.getinfo("bot.py")
            if bot_info.file_size > MAX_BOT_SOURCE_BYTES:
                return False, f"bot.py exceeds {MAX_BOT_SOURCE_BYTES} byte limit"

            with archive.open(bot_info) as bot_file:
                source = bot_file.read().decode("utf-8")
    except zipfile.BadZipFile:
        return False, "Upload is not a valid zip archive"
    except UnicodeDecodeError:
        return False, "bot.py must be valid UTF-8 text"
    except KeyError:
        return False, "bot.py must be at the root of the zip"

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
