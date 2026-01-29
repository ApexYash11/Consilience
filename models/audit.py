"""Audit models."""
from pydantic import BaseModel
from datetime import datetime
from typing import Dict, Any
from uuid import UUID, uuid4


class AuditEntry(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    actor: str
    action: str
    resource_type: str
    resource_id: str | None = None
    details: Dict[str, Any] = {}
