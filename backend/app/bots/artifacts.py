from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

import boto3
from botocore.config import Config as BotoConfig

from app.bots.config import ArtifactConfig


@dataclass(frozen=True)
class ArtifactRef:
    backend: str
    filename: str
    sha256: str
    size_bytes: int
    bucket: str | None = None
    key: str | None = None
    path: str | None = None

    def to_dict(self) -> dict:
        return {
            "backend": self.backend,
            "filename": self.filename,
            "sha256": self.sha256,
            "size_bytes": self.size_bytes,
            "bucket": self.bucket,
            "key": self.key,
            "path": self.path,
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "ArtifactRef":
        return cls(
            backend=payload["backend"],
            filename=payload["filename"],
            sha256=payload["sha256"],
            size_bytes=payload["size_bytes"],
            bucket=payload.get("bucket"),
            key=payload.get("key"),
            path=payload.get("path"),
        )


class ArtifactStore:
    def __init__(self, config: ArtifactConfig) -> None:
        self.config = config
        self._s3_client = None

    def store(self, *, bot_id: str, filename: str, payload: bytes) -> ArtifactRef:
        safe_filename = Path(filename).name or "bot.zip"
        sha256 = hashlib.sha256(payload).hexdigest()
        size_bytes = len(payload)
        if self.config.backend == "filesystem":
            artifact_dir = self.config.artifacts_dir / bot_id / sha256
            artifact_dir.mkdir(parents=True, exist_ok=True)
            path = artifact_dir / safe_filename
            if not path.exists():
                path.write_bytes(payload)
            return ArtifactRef(
                backend="filesystem",
                filename=safe_filename,
                sha256=sha256,
                size_bytes=size_bytes,
                path=str(path),
            )
        if self.config.backend == "s3":
            bucket = self._require(self.config.s3_bucket, "S3_BUCKET")
            key = f"{bot_id}/{sha256}/{safe_filename}"
            self._s3().put_object(
                Bucket=bucket,
                Key=key,
                Body=payload,
                ContentType="application/zip",
            )
            return ArtifactRef(
                backend="s3",
                filename=safe_filename,
                sha256=sha256,
                size_bytes=size_bytes,
                bucket=bucket,
                key=key,
            )
        raise ValueError(f"Unsupported artifact backend: {self.config.backend}")

    def fetch(self, ref: ArtifactRef) -> Path:
        if ref.backend == "filesystem":
            if not ref.path:
                raise ValueError("filesystem artifact missing path")
            path = Path(ref.path)
            if not path.exists():
                raise FileNotFoundError(path)
            return path
        if ref.backend == "s3":
            bucket = self._require(ref.bucket, "S3_BUCKET")
            key = self._require(ref.key, "artifact key")
            cache_dir = self.config.cache_dir / ref.sha256
            cache_dir.mkdir(parents=True, exist_ok=True)
            target = cache_dir / ref.filename
            if not target.exists():
                self._s3().download_file(bucket, key, str(target))
            return target
        raise ValueError(f"Unsupported artifact backend: {ref.backend}")

    def _s3(self):
        if self._s3_client is None:
            endpoint = self._require(self.config.s3_endpoint, "S3_ENDPOINT")
            s3_config = BotoConfig(
                s3={"addressing_style": "path" if self.config.s3_force_path_style else "virtual"}
            )
            self._s3_client = boto3.client(
                "s3",
                endpoint_url=endpoint,
                region_name=self.config.s3_region,
                aws_access_key_id=self.config.s3_access_key,
                aws_secret_access_key=self.config.s3_secret_key,
                config=s3_config,
            )
        return self._s3_client

    @staticmethod
    def _require(value: str | None, name: str) -> str:
        if not value:
            raise ValueError(f"Missing required config: {name}")
        return value
