from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from app.bots.build import BotBuildError, build_bot_image_from_archive, inspect_bot_archive
from app.bots.security import MAX_REQUIREMENTS_BYTES


def _build_zip(path: Path, files: dict[str, str]) -> Path:
    with zipfile.ZipFile(path, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return path


def test_inspect_bot_archive_with_requirements(tmp_path: Path) -> None:
    zip_path = _build_zip(
        tmp_path / "bot.zip",
        {
            "bot.py": "class PokerBot:\n    def act(self, state):\n        return {'action': 'check'}",
            "requirements.txt": "requests==2.32.3",
        },
    )
    info = inspect_bot_archive(zip_path)
    assert info.entrypoint == "bot.py"
    assert info.requirements_text == "requests==2.32.3"
    assert info.requirements_hash is not None


def test_inspect_bot_archive_nested_entrypoint(tmp_path: Path) -> None:
    zip_path = _build_zip(
        tmp_path / "bot.zip",
        {
            "nested/bot.py": "class PokerBot:\n    def act(self, state):\n        return {'action': 'check'}",
        },
    )
    info = inspect_bot_archive(zip_path)
    assert info.entrypoint == "nested/bot.py"
    assert info.requirements_text is None
    assert info.requirements_hash is None


def test_inspect_bot_archive_rejects_missing_bot(tmp_path: Path) -> None:
    zip_path = _build_zip(tmp_path / "bot.zip", {"readme.txt": "no bot"})
    with pytest.raises(BotBuildError, match="bot.py must exist"):
        inspect_bot_archive(zip_path)


def test_inspect_bot_archive_rejects_large_requirements(tmp_path: Path) -> None:
    zip_path = _build_zip(
        tmp_path / "bot.zip",
        {
            "bot.py": "class PokerBot:\n    def act(self, state):\n        return {'action': 'check'}",
            "requirements.txt": "x" * (MAX_REQUIREMENTS_BYTES + 1),
        },
    )
    with pytest.raises(BotBuildError, match="requirements.txt exceeds"):
        inspect_bot_archive(zip_path)


def test_build_bot_image_from_archive_builds_context(tmp_path: Path, monkeypatch) -> None:
    repo_root = tmp_path / "repo"
    runtime_dir = repo_root / "runtime" / "bot_runner"
    runtime_dir.mkdir(parents=True)
    (runtime_dir / "bot_server.py").write_text("print('hello')", encoding="utf-8")
    (runtime_dir / "Dockerfile").write_text("FROM python:3.12-slim\n", encoding="utf-8")

    zip_path = _build_zip(
        tmp_path / "bot.zip",
        {
            "bot.py": "class PokerBot:\n    def act(self, state):\n        return {'action': 'check'}",
            "requirements.txt": "requests==2.32.3",
        },
    )

    seen = {}

    def fake_build_bot_image(*, repo_root, build_context, image_tag, docker_bin, dockerfile):
        seen["context"] = build_context
        assert (build_context / "bot_server.py").exists()
        assert (build_context / "Dockerfile").exists()
        assert (build_context / "bot" / "bot.py").exists()
        assert (build_context / "requirements.txt").read_text(encoding="utf-8") == "requests==2.32.3"
        assert dockerfile == build_context / "Dockerfile"
        assert image_tag == "poker-bot:test"
        assert docker_bin == "docker"

    monkeypatch.setattr("app.bots.build.build_bot_image", fake_build_bot_image)

    info = build_bot_image_from_archive(
        artifact_path=zip_path,
        repo_root=repo_root,
        image_tag="poker-bot:test",
        docker_bin="docker",
    )
    assert info.entrypoint == "bot.py"
    assert info.requirements_hash is not None
    assert seen["context"] is not None
