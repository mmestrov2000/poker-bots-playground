from pathlib import Path
from uuid import uuid4


def save_upload(*, seat_id: str, filename: str, payload: bytes, uploads_dir: Path) -> Path:
    """Store uploaded bot archive in runtime uploads directory."""
    seat_dir = uploads_dir / seat_id
    seat_dir.mkdir(parents=True, exist_ok=True)
    destination = seat_dir / f"{uuid4().hex}_{filename}"
    destination.write_bytes(payload)
    return destination
