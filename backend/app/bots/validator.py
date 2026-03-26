from __future__ import annotations

import io
import zipfile

from app.bots.manifest import parse_manifest, select_manifest_member
from app.bots.security import validate_archive_infos


def validate_bot_archive(payload: bytes) -> tuple[bool, str | None]:
    if not payload:
        return False, "Upload payload is empty"

    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            is_valid, error_message = validate_archive_infos(archive.infolist())
            if not is_valid:
                return False, error_message

            manifest_member, manifest_error = select_manifest_member(archive.namelist())
            if manifest_member is None:
                return False, manifest_error or "bot.json must exist at zip root or one top-level folder"

            manifest_info = archive.getinfo(manifest_member)
            with archive.open(manifest_info) as manifest_file:
                manifest, error = parse_manifest(
                    raw_manifest=manifest_file.read(),
                    manifest_member=manifest_member,
                    archive_names=archive.namelist(),
                )
            if manifest is None:
                return False, error or "Invalid bot manifest"
            return True, None
    except zipfile.BadZipFile:
        return False, "Upload is not a valid zip archive"
