from __future__ import annotations

from pathlib import Path, PurePosixPath
from stat import S_ISLNK
from zipfile import ZipFile, ZipInfo


MAX_UPLOAD_BYTES = 10 * 1024 * 1024
MAX_ARCHIVE_MEMBERS = 128
MAX_ARCHIVE_FILE_BYTES = 1 * 1024 * 1024
MAX_ARCHIVE_UNCOMPRESSED_BYTES = 2 * 1024 * 1024
MAX_BOT_SOURCE_BYTES = 256 * 1024


def validate_archive_infos(infos: list[ZipInfo]) -> tuple[bool, str | None]:
    if len(infos) > MAX_ARCHIVE_MEMBERS:
        return False, f"Archive contains too many files (max {MAX_ARCHIVE_MEMBERS})"

    seen: set[PurePosixPath] = set()
    total_uncompressed = 0
    for info in infos:
        normalized, path_error = normalize_archive_member(info.filename)
        if path_error:
            return False, path_error

        if normalized in seen:
            return False, f"Archive contains duplicate entry: {normalized.as_posix()}"
        seen.add(normalized)

        if is_symlink_entry(info):
            return False, "Archive symlinks are not allowed"
        if info.is_dir():
            continue

        if info.file_size > MAX_ARCHIVE_FILE_BYTES:
            return False, f"Archive file exceeds {MAX_ARCHIVE_FILE_BYTES} byte limit"
        total_uncompressed += info.file_size
        if total_uncompressed > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
            return (
                False,
                f"Archive uncompressed size exceeds {MAX_ARCHIVE_UNCOMPRESSED_BYTES} byte limit",
            )

    return True, None


def extract_archive_safely(archive: ZipFile, destination: Path) -> None:
    infos = archive.infolist()
    is_valid, error = validate_archive_infos(infos)
    if not is_valid:
        raise ValueError(error or "Invalid archive")

    extracted_total = 0
    for info in infos:
        normalized, _ = normalize_archive_member(info.filename)
        if normalized is None:
            raise ValueError("Invalid archive member path")

        target_path = destination / Path(*normalized.parts)
        if info.is_dir():
            target_path.mkdir(parents=True, exist_ok=True)
            continue

        target_path.parent.mkdir(parents=True, exist_ok=True)
        with archive.open(info, "r") as source, target_path.open("wb") as target:
            while chunk := source.read(64 * 1024):
                extracted_total += len(chunk)
                if extracted_total > MAX_ARCHIVE_UNCOMPRESSED_BYTES:
                    raise ValueError(
                        f"Archive uncompressed size exceeds {MAX_ARCHIVE_UNCOMPRESSED_BYTES} byte limit"
                    )
                target.write(chunk)


def normalize_archive_member(filename: str) -> tuple[PurePosixPath | None, str | None]:
    if not filename:
        return None, "Archive contains an empty entry name"
    if filename.startswith("/"):
        return None, "Archive contains absolute paths"
    if "\\" in filename:
        return None, "Archive contains unsupported path separators"

    normalized = PurePosixPath(filename)
    if any(part in {"", ".", ".."} for part in normalized.parts):
        return None, "Archive contains unsafe paths"

    return normalized, None


def is_symlink_entry(info: ZipInfo) -> bool:
    mode = (info.external_attr >> 16) & 0o170000
    return S_ISLNK(mode)
