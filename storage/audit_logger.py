import json
from datetime import datetime
from typing import Dict, List
from models import AuditEntry

class AuditLogger:
    """Simple audit logger that appends JSON lines to a file and keeps an in-memory list."""

    def __init__(self, path: str):
        self.path = path
        self._in_memory: List[Dict] = []

    def _entry(self, actor: str, action: str, details: Dict) -> AuditEntry:
        return AuditEntry(timestamp=datetime.utcnow(), actor=actor, action=action, details=details)

    def log(self, actor: str, action: str, details: Dict):
        entry = self._entry(actor, action, details)
        d = entry.to_dict()
        self._in_memory.append(d)
        try:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(d) + "\n")
        except Exception:
            # Best-effort file logging; do not raise for demo
            pass

    def all(self) -> List[Dict]:
        return list(self._in_memory)
