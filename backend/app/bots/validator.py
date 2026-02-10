from __future__ import annotations

import ast
import io
import zipfile


def validate_bot_archive(payload: bytes) -> tuple[bool, str | None]:
    if not payload:
        return False, "Upload payload is empty"

    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            names = set(archive.namelist())
            if "bot.py" not in names:
                return False, "bot.py must be at the root of the zip"

            with archive.open("bot.py") as bot_file:
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
