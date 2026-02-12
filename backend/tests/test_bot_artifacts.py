from pathlib import Path

import pytest

from app.bots.artifacts import ArtifactRef, ArtifactStore
from app.bots.config import ArtifactConfig


class FakeS3:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}

    def put_object(self, *, Bucket: str, Key: str, Body: bytes, ContentType: str | None = None) -> None:
        self.objects[(Bucket, Key)] = Body

    def download_file(self, Bucket: str, Key: str, Filename: str) -> None:
        Path(Filename).write_bytes(self.objects[(Bucket, Key)])


def test_filesystem_artifact_store(tmp_path: Path) -> None:
    config = ArtifactConfig(
        backend="filesystem",
        artifacts_dir=tmp_path / "artifacts",
        cache_dir=tmp_path / "cache",
        s3_endpoint=None,
        s3_bucket=None,
        s3_region=None,
        s3_access_key=None,
        s3_secret_key=None,
        s3_force_path_style=True,
    )
    store = ArtifactStore(config)
    payload = b"zip-bytes"
    ref = store.store(bot_id="bot1", filename="bot.zip", payload=payload)
    path = store.fetch(ref)
    assert path.exists()
    assert path.read_bytes() == payload
    assert "bot1" in str(path)


def test_s3_artifact_store_with_fake_client(tmp_path: Path) -> None:
    config = ArtifactConfig(
        backend="s3",
        artifacts_dir=tmp_path / "artifacts",
        cache_dir=tmp_path / "cache",
        s3_endpoint="http://example",
        s3_bucket="bucket",
        s3_region="us-east-1",
        s3_access_key="key",
        s3_secret_key="secret",
        s3_force_path_style=True,
    )
    store = ArtifactStore(config)
    store._s3_client = FakeS3()
    payload = b"zip-bytes"
    ref = store.store(bot_id="bot1", filename="bot.zip", payload=payload)
    path = store.fetch(ref)
    assert path.read_bytes() == payload


def test_s3_artifact_store_requires_bucket(tmp_path: Path) -> None:
    config = ArtifactConfig(
        backend="s3",
        artifacts_dir=tmp_path / "artifacts",
        cache_dir=tmp_path / "cache",
        s3_endpoint="http://example",
        s3_bucket=None,
        s3_region="us-east-1",
        s3_access_key="key",
        s3_secret_key="secret",
        s3_force_path_style=True,
    )
    store = ArtifactStore(config)
    store._s3_client = FakeS3()
    with pytest.raises(ValueError, match="S3_BUCKET"):
        store.store(bot_id="bot1", filename="bot.zip", payload=b"zip-bytes")


def test_filesystem_fetch_requires_path(tmp_path: Path) -> None:
    config = ArtifactConfig(
        backend="filesystem",
        artifacts_dir=tmp_path / "artifacts",
        cache_dir=tmp_path / "cache",
        s3_endpoint=None,
        s3_bucket=None,
        s3_region=None,
        s3_access_key=None,
        s3_secret_key=None,
        s3_force_path_style=True,
    )
    store = ArtifactStore(config)
    ref = ArtifactRef(backend="filesystem", filename="bot.zip", sha256="abc", size_bytes=3)
    with pytest.raises(ValueError, match="missing path"):
        store.fetch(ref)


def test_s3_fetch_requires_key(tmp_path: Path) -> None:
    config = ArtifactConfig(
        backend="s3",
        artifacts_dir=tmp_path / "artifacts",
        cache_dir=tmp_path / "cache",
        s3_endpoint="http://example",
        s3_bucket="bucket",
        s3_region="us-east-1",
        s3_access_key="key",
        s3_secret_key="secret",
        s3_force_path_style=True,
    )
    store = ArtifactStore(config)
    store._s3_client = FakeS3()
    ref = ArtifactRef(
        backend="s3",
        filename="bot.zip",
        sha256="abc",
        size_bytes=3,
        bucket="bucket",
        key=None,
    )
    with pytest.raises(ValueError, match="artifact key"):
        store.fetch(ref)
