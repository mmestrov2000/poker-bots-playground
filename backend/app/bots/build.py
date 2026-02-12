from __future__ import annotations

import hashlib
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

from app.bots.container_runtime import build_bot_image
from app.bots.security import MAX_REQUIREMENTS_BYTES, extract_archive_safely
from app.bots.validator import select_bot_member, select_requirements_member


class BotBuildError(RuntimeError):
    pass


@dataclass(frozen=True)
class BotArchiveInfo:
    entrypoint: str
    requirements_text: str | None
    requirements_hash: str | None


def inspect_bot_archive(artifact_path: Path) -> BotArchiveInfo:
    with zipfile.ZipFile(artifact_path, "r") as archive:
        return _read_archive_info(archive)


def build_bot_image_from_archive(
    *,
    artifact_path: Path,
    repo_root: Path,
    image_tag: str,
    docker_bin: str,
) -> BotArchiveInfo:
    with tempfile.TemporaryDirectory(prefix="bot-build-") as temp_dir:
        build_context = Path(temp_dir)
        extract_dir = build_context / "extracted"
        extract_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(artifact_path, "r") as archive:
            info = _read_archive_info(archive)
            extract_archive_safely(archive, extract_dir)

        runtime_dir = repo_root / "runtime" / "bot_runner"
        bot_server = runtime_dir / "bot_server.py"
        dockerfile = runtime_dir / "Dockerfile"
        if not bot_server.exists():
            raise BotBuildError("bot_server.py not found")
        if not dockerfile.exists():
            raise BotBuildError("Dockerfile not found")
        shutil.copy(bot_server, build_context / "bot_server.py")
        shutil.copy(dockerfile, build_context / "Dockerfile")
        (build_context / "requirements.txt").write_text(info.requirements_text or "", encoding="utf-8")
        shutil.copytree(extract_dir, build_context / "bot", dirs_exist_ok=True)

        build_bot_image(
            repo_root=repo_root,
            build_context=build_context,
            image_tag=image_tag,
            docker_bin=docker_bin,
            dockerfile=build_context / "Dockerfile",
        )
        return info


def _read_archive_info(archive: zipfile.ZipFile) -> BotArchiveInfo:
    bot_member, bot_error = select_bot_member(archive.namelist())
    if bot_member is None:
        raise BotBuildError(bot_error or "bot.py was not found in the zip")
    requirements_member, req_error = select_requirements_member(archive.namelist())
    if req_error:
        raise BotBuildError(req_error)
    requirements_text = None
    requirements_hash = None
    if requirements_member:
        requirements_info = archive.getinfo(requirements_member)
        if requirements_info.file_size > MAX_REQUIREMENTS_BYTES:
            raise BotBuildError(f"requirements.txt exceeds {MAX_REQUIREMENTS_BYTES} byte limit")
        requirements_bytes = archive.read(requirements_member)
        try:
            requirements_text = requirements_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise BotBuildError("requirements.txt must be valid UTF-8 text") from exc
        requirements_hash = hashlib.sha256(requirements_bytes).hexdigest()
    return BotArchiveInfo(
        entrypoint=bot_member,
        requirements_text=requirements_text,
        requirements_hash=requirements_hash,
    )
