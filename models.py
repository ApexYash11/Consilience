from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List

@dataclass
class ResearchTask:
    id: str
    title: str
    description: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
        }

@dataclass
class AgentSpec:
    name: str
    role: str
    capabilities: List[str] = field(default_factory=list)

@dataclass
class AuditEntry:
    timestamp: datetime
    actor: str
    action: str
    details: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "actor": self.actor,
            "action": self.action,
            "details": self.details,
        }
