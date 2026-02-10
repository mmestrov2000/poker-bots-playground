from pathlib import Path


class HandStore:
    def __init__(self, base_dir: Path | None = None) -> None:
        if base_dir is None:
            repo_root = Path(__file__).resolve().parents[3]
            base_dir = repo_root / "runtime" / "hands"
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save_hand(self, hand_id: str, content: str) -> Path:
        path = self.base_dir / f"{hand_id}.txt"
        path.write_text(content, encoding="utf-8")
        return path

    def load_hand(self, hand_id: str) -> str | None:
        path = self.base_dir / f"{hand_id}.txt"
        if not path.exists():
            return None
        return path.read_text(encoding="utf-8")

    def clear(self) -> None:
        for path in self.base_dir.glob("*.txt"):
            path.unlink(missing_ok=True)
