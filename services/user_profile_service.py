"""Helpers for managing user interest profiles (LightMem-backed)."""

from __future__ import annotations

from typing import List, Tuple

from services.memory.facade import MEMORY_SERVICE

PROFILE_SESSION_PREFIX = "user:"
PROFILE_TOPIC = "profile.interest"


def _session_id(user_id: str) -> str:
    return f"{PROFILE_SESSION_PREFIX}{user_id}"


def list_interests(user_id: str) -> List[str]:
    summaries = MEMORY_SERVICE.get_session_summaries(_session_id(user_id))
    tags: List[str] = []
    for entry in summaries:
        if entry.topic != PROFILE_TOPIC:
            continue
        for h in entry.highlights:
            for part in h.replace("관심 티커:", "").replace("관심 산업/리스크:", "").split(","):
                clean = part.strip()
                if clean and clean not in tags:
                    tags.append(clean)
    return tags


def _build_entry(user_id: str, tags: List[str]):
    highlights = []
    if tags:
        highlights.append("관심 티커: " + ", ".join(tags))
    return {
        "session_id": _session_id(user_id),
        "topic": PROFILE_TOPIC,
        "highlights": highlights,
    }


def upsert_interests(user_id: str, tags: List[str]) -> List[str]:
    tags = [t.strip() for t in tags if t and t.strip()]
    unique_tags = []
    seen = set()
    for t in tags:
        if t.lower() in seen:
            continue
        seen.add(t.lower())
        unique_tags.append(t)
    entry = _build_entry(user_id, unique_tags)
    MEMORY_SERVICE.save_session_summary(
        session_id=entry["session_id"],
        topic=PROFILE_TOPIC,
        highlights=entry["highlights"],
        metadata={"user_id": user_id, "kind": "user_profile"},
        expires_at=MEMORY_SERVICE.profile_expiry(),
    )
    return list_interests(user_id)


def add_interest(user_id: str, tag: str) -> List[str]:
    tags = list_interests(user_id)
    if tag and tag.strip() and tag.strip() not in tags:
        tags.append(tag.strip())
    return upsert_interests(user_id, tags)


def remove_interest(user_id: str, tag: str) -> List[str]:
    tags = [t for t in list_interests(user_id) if t.lower() != tag.strip().lower()]
    return upsert_interests(user_id, tags)


__all__ = ["list_interests", "add_interest", "remove_interest", "upsert_interests"]
