from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from app.db.bootstrap import maybe_bootstrap_shared_schema
from app.db.config import DBConfig


def _config(enabled: bool = True, password: str = "secret") -> DBConfig:
    return DBConfig(
        host="localhost",
        port=5432,
        name="poker_bots",
        admin_user="postgres",
        admin_password="postgres",
        shared_schema="shared",
        private_schema_prefix="bot_",
        sslmode="disable",
        shared_aggregator_user="shared_aggregator",
        shared_aggregator_password=password,
        enabled=enabled,
    )


def _write_bootstrap(repo_root: Path) -> None:
    script_path = repo_root / "backend" / "scripts" / "db_bootstrap.py"
    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text("#!/usr/bin/env python\n", encoding="utf-8")


def test_bootstrap_skips_when_db_disabled(monkeypatch, tmp_path: Path) -> None:
    _write_bootstrap(tmp_path)

    def bomb(*args, **kwargs):
        raise AssertionError("subprocess.run should not be called")

    monkeypatch.setattr(subprocess, "run", bomb)
    maybe_bootstrap_shared_schema(repo_root=tmp_path, config=_config(enabled=False))


def test_bootstrap_skips_when_env_disabled(monkeypatch, tmp_path: Path) -> None:
    _write_bootstrap(tmp_path)
    monkeypatch.setenv("DB_BOOTSTRAP_ON_STARTUP", "0")

    def bomb(*args, **kwargs):
        raise AssertionError("subprocess.run should not be called")

    monkeypatch.setattr(subprocess, "run", bomb)
    maybe_bootstrap_shared_schema(repo_root=tmp_path, config=_config())


def test_bootstrap_retries_and_passes_password(monkeypatch, tmp_path: Path) -> None:
    _write_bootstrap(tmp_path)
    monkeypatch.setenv("DB_BOOTSTRAP_ON_STARTUP", "1")
    monkeypatch.setenv("DB_BOOTSTRAP_RETRIES", "3")
    monkeypatch.setenv("DB_BOOTSTRAP_DELAY_SECONDS", "0")

    calls: list[dict] = []

    def fake_run(cmd, check, cwd, env):
        calls.append({"cmd": cmd, "env": env, "cwd": cwd})
        if len(calls) < 3:
            raise subprocess.CalledProcessError(1, cmd)
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)

    maybe_bootstrap_shared_schema(repo_root=tmp_path, config=_config(password="secret"))

    assert len(calls) == 3
    last_cmd = calls[-1]["cmd"]
    assert "--shared" in last_cmd
    assert "--shared-aggregator-password" in last_cmd
    assert "secret" in last_cmd
    assert calls[-1]["env"]["DB_SHARED_AGGREGATOR_PASSWORD"] == "secret"


def test_bootstrap_errors_when_missing_script(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="db_bootstrap.py not found"):
        maybe_bootstrap_shared_schema(repo_root=tmp_path, config=_config())
