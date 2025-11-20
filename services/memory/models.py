"""Dataclasses and helpers shared across the LightMem-inspired pipeline.

These models deliberately avoid persistence/storage logic so they can be re-used
by both the short-term cache (Redis/PlanStore) and the long-term vector store.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, Iterable, List, Mapping, Optional, Sequence
import uuid


UTC = timezone.utc


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class SessionSummaryEntry:
    """Lightweight snapshot of a conversation or watchlist run.

    Parameters
    ----------
    session_id:
        Logical identifier of the session (watchlist chat, report build id, ...).
    topic:
        High level topic used for grouping (예: "watchlist.rule", "report.samsungSDI").
    highlights:
        Short bullet-style notes extracted from the conversation.
    expires_at:
        Expiration timestamp (UTC). Once past this moment the entry should be
        flushed to the long-term candidate queue or deleted.
    metadata:
        Optional arbitrary dictionary for downstream consumers (e.g. plan tier,
        rule identifiers).
    created_at / updated_at:
        Timestamps for auditing.
    """

    session_id: str
    topic: str
    highlights: Sequence[str]
    expires_at: datetime
    metadata: Mapping[str, str] = field(default_factory=dict)
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)

    def is_expired(self, *, at: Optional[datetime] = None) -> bool:
        reference = at or _now()
        return reference >= self.expires_at

    def as_dict(self) -> Dict[str, object]:
        return {
            "session_id": self.session_id,
            "topic": self.topic,
            "highlights": list(self.highlights),
            "expires_at": self.expires_at.isoformat(),
            "metadata": dict(self.metadata),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "SessionSummaryEntry":
        return cls(
            session_id=str(payload.get("session_id")),
            topic=str(payload.get("topic")),
            highlights=list(payload.get("highlights") or []),
            expires_at=datetime.fromisoformat(str(payload.get("expires_at"))),
            metadata=dict(payload.get("metadata") or {}),
            created_at=datetime.fromisoformat(str(payload.get("created_at"))) if payload.get("created_at") else _now(),
            updated_at=datetime.fromisoformat(str(payload.get("updated_at"))) if payload.get("updated_at") else _now(),
        )


@dataclass(frozen=True)
class MemoryRecord:
    """Representation of a long-term memory item stored in Qdrant (or similar)."""

    tenant_id: str
    user_id: str
    topic: str
    summary: str
    embedding: Sequence[float]
    importance_score: float
    created_at: datetime = field(default_factory=_now)
    updated_at: datetime = field(default_factory=_now)
    record_id: str = field(default_factory=lambda: uuid.uuid4().hex)

    def as_payload(self) -> Dict[str, object]:
        return {
            "record_id": self.record_id,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "topic": self.topic,
            "summary": self.summary,
            "embedding": list(self.embedding),
            "importance_score": self.importance_score,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


def default_ttl(hours: int = 2) -> datetime:
    """Utility used by the session store to compute expiry timestamps."""

    return _now() + timedelta(hours=hours)
