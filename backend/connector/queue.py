import json
import threading
import uuid
from pathlib import Path
from typing import Any


class FileOutboxQueue:
    """Simple file-backed outbox: JSON lines appended under QUEUE_DIR."""

    def __init__(self, queue_dir: str) -> None:
        self.queue_dir = Path(queue_dir)
        self.queue_dir.mkdir(parents=True, exist_ok=True)
        self.pending_path = self.queue_dir / "pending.jsonl"
        self.synced_path = self.queue_dir / "synced.jsonl"
        self._lock = threading.Lock()

    def push(self, record: dict[str, Any]) -> dict[str, Any]:
        """Assign an id and append a record to the outbox."""
        item = dict(record)
        item.setdefault("id", uuid.uuid4().hex)
        with self._lock:
            with self.pending_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(item, default=str) + "\n")
        return item

    def _read(self, path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        items: list[dict[str, Any]] = []
        try:
            with path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        items.append(json.loads(line))
                    except (ValueError, TypeError):
                        continue
        except OSError:
            return []
        return items

    def pop_all(self) -> list[dict[str, Any]]:
        """Return all pending records without removing them."""
        with self._lock:
            return self._read(self.pending_path)

    def mark_synced(self, items: list[dict[str, Any]]) -> None:
        """Move successfully uploaded records to the synced log."""
        if not items:
            return
        ids = {item.get("id") for item in items}
        with self._lock:
            with self.synced_path.open("a", encoding="utf-8") as handle:
                for item in items:
                    handle.write(json.dumps(item, default=str) + "\n")
            remaining = [item for item in self._read(self.pending_path) if item.get("id") not in ids]
            if remaining:
                with self.pending_path.open("w", encoding="utf-8") as handle:
                    for item in remaining:
                        handle.write(json.dumps(item, default=str) + "\n")
            else:
                self.pending_path.unlink(missing_ok=True)