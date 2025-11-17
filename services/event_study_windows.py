from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from models.event_study import EventWindow


@dataclass(frozen=True)
class EventWindowPreset:
    key: str
    label: str
    start: int
    end: int
    description: Optional[str]
    significance: float
    is_default: bool


_FALLBACK_WINDOWS: Tuple[EventWindowPreset, ...] = (
    EventWindowPreset(
        key="window_short",
        label="[-5,+5]",
        start=-5,
        end=5,
        description="Short reaction window for rapid disclosures",
        significance=0.1,
        is_default=False,
    ),
    EventWindowPreset(
        key="window_medium",
        label="[-5,+20]",
        start=-5,
        end=20,
        description="Default drift window used by dashboards",
        significance=0.1,
        is_default=True,
    ),
    EventWindowPreset(
        key="window_long",
        label="[-10,+30]",
        start=-10,
        end=30,
        description="Extended observation window for structural events",
        significance=0.1,
        is_default=False,
    ),
)


def list_event_window_presets(db: Optional[Session] = None) -> List[EventWindowPreset]:
    if db is None:
        return list(_FALLBACK_WINDOWS)

    rows = (
        db.query(EventWindow)
        .order_by(EventWindow.display_order.asc(), EventWindow.key.asc())
        .all()
    )
    if not rows:
        return list(_FALLBACK_WINDOWS)
    presets: List[EventWindowPreset] = []
    for row in rows:
        presets.append(
            EventWindowPreset(
                key=row.key,
                label=row.label,
                start=int(row.start_offset),
                end=int(row.end_offset),
                description=row.description,
                significance=float(row.default_significance or 0.1),
                is_default=bool(row.is_default),
            )
        )
    return presets


def get_event_window_preset(window_key: Optional[str], db: Optional[Session] = None) -> EventWindowPreset:
    normalized = (window_key or "").strip().lower()
    presets = list_event_window_presets(db)
    if normalized:
        for preset in presets:
            if preset.key.lower() == normalized:
                return preset
    for preset in presets:
        if preset.is_default:
            return preset
    return presets[0]


def get_event_window_span(db: Optional[Session] = None) -> Tuple[int, int]:
    presets = list_event_window_presets(db)
    return (
        min(p.start for p in presets),
        max(p.end for p in presets),
    )


def get_default_window_key(db: Optional[Session] = None) -> str:
    preset = get_event_window_preset(None, db)
    return preset.key


def format_window_label(start: int, end: int) -> str:
    return f"[{start},{end}]"
