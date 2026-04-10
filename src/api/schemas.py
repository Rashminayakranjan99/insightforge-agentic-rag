# src/api/schemas.py
"""Request/Response schemas for the API."""

from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any


@dataclass
class ChatRequest:
    query: str
    session_id: str = "default"

    @classmethod
    def from_dict(cls, d: dict) -> "ChatRequest":
        return cls(
            query=d.get("query", ""),
            session_id=d.get("session_id", "default"),
        )


@dataclass
class ChatResponse:
    narrative: str
    chart_config: Optional[Dict[str, Any]] = None
    analysis_type: str = ""
    provider: str = ""
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class UploadResponse:
    success: bool
    filename: str = ""
    profile: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DashboardSaveRequest:
    name: str
    chart_ids: List[str] = field(default_factory=list)
    session_id: str = "default"

    @classmethod
    def from_dict(cls, d: dict) -> "DashboardSaveRequest":
        return cls(
            name=d.get("name", "My Dashboard"),
            chart_ids=d.get("chart_ids", []),
            session_id=d.get("session_id", "default"),
        )
