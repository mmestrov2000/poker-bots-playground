from pathlib import Path

from app.auth.config import AuthSettings


def test_auth_settings_default_db_path_uses_repo_runtime(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("APP_RUNTIME_DIR", raising=False)
    monkeypatch.delenv("APP_AUTH_DB_PATH", raising=False)

    settings = AuthSettings.from_env(repo_root=tmp_path)

    assert settings.db_path == tmp_path / "runtime" / "auth.sqlite3"
    assert (tmp_path / "runtime").exists()


def test_auth_settings_prefers_explicit_runtime_dir(monkeypatch, tmp_path: Path):
    runtime_dir = tmp_path / "persistent" / "runtime"
    monkeypatch.setenv("APP_RUNTIME_DIR", str(runtime_dir))
    monkeypatch.delenv("APP_AUTH_DB_PATH", raising=False)

    settings = AuthSettings.from_env(repo_root=tmp_path)

    assert settings.db_path == runtime_dir / "auth.sqlite3"
    assert runtime_dir.exists()


def test_auth_settings_migrates_legacy_backend_runtime_db(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("APP_RUNTIME_DIR", raising=False)
    monkeypatch.delenv("APP_AUTH_DB_PATH", raising=False)
    legacy_db = tmp_path / "backend" / "runtime" / "auth.sqlite3"
    legacy_db.parent.mkdir(parents=True, exist_ok=True)
    legacy_db.write_bytes(b"legacy-db")

    settings = AuthSettings.from_env(repo_root=tmp_path)

    new_db = tmp_path / "runtime" / "auth.sqlite3"
    assert settings.db_path == new_db
    assert new_db.exists()
    assert new_db.read_bytes() == b"legacy-db"
    assert not legacy_db.exists()

