"""Utilities for tracking alert preset launches."""

from __future__ import annotations

import json
import threading
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence

STORE_PATH = Path("uploads") / "admin" / "alert_preset_usage.jsonl"
_LOCK = threading.RLock()

from .presets import PRESETS


@dataclass(frozen=True)
class PresetUsageRecord:
    preset_id: str
    bundle: Optional[str]
    plan_tier: Optional[str]
    channel_types: Sequence[str]
    user_id: Optional[str]
    org_id: Optional[str]
    timestamp: datetime
    rule_id: Optional[str] = None

    def to_dict(self) -> Dict[str, object]:
        return {
            "presetId": self.preset_id,
            "bundle": self.bundle,
            "planTier": self.plan_tier,
            "channelTypes": list(self.channel_types),
            "userId": self.user_id,
            "orgId": self.org_id,
            "timestamp": self.timestamp.isoformat(),
            "ruleId": self.rule_id,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> Optional["PresetUsageRecord"]:
        try:
            timestamp_value = payload.get("timestamp")
            if isinstance(timestamp_value, str):
                timestamp = datetime.fromisoformat(timestamp_value)
            else:
                return None
            bundle_value = payload.get("bundle")
            plan_value = payload.get("planTier")
            user_value = payload.get("userId")
            org_value = payload.get("orgId")
            rule_value = payload.get("ruleId")
            return cls(
                preset_id=str(payload.get("presetId")),
                bundle=str(bundle_value) if bundle_value else None,
                plan_tier=str(plan_value) if plan_value else None,
                channel_types=tuple(payload.get("channelTypes") or []),
                user_id=str(user_value) if user_value else None,
                org_id=str(org_value) if org_value else None,
                timestamp=timestamp,
                rule_id=str(rule_value) if rule_value else None,
            )
        except Exception:
            return None


def _ensure_store_dir() -> None:
    STORE_PATH.parent.mkdir(parents=True, exist_ok=True)


def record_usage(
    *,
    preset_id: str,
    bundle: Optional[str],
    plan_tier: Optional[str],
    channel_types: Iterable[str],
    user_id: Optional[uuid.UUID],
    org_id: Optional[uuid.UUID],
    rule_id: Optional[uuid.UUID] = None,
) -> None:
    """Append a launch record for analytics/ops dashboards."""

    entry = PresetUsageRecord(
        preset_id=preset_id,
        bundle=bundle,
        plan_tier=plan_tier,
        channel_types=tuple(sorted({channel.strip().lower() for channel in channel_types if channel})),
        user_id=str(user_id) if user_id else None,
        org_id=str(org_id) if org_id else None,
        timestamp=datetime.now(timezone.utc),
        rule_id=str(rule_id) if rule_id else None,
    )
    line = json.dumps(entry.to_dict(), ensure_ascii=False)
    with _LOCK:
        _ensure_store_dir()
        with STORE_PATH.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")


def _load_entries() -> List[PresetUsageRecord]:
    if not STORE_PATH.exists():
        return []
    entries: List[PresetUsageRecord] = []
    with _LOCK:
        try:
            for line in STORE_PATH.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                record = PresetUsageRecord.from_dict(payload)
                if record:
                    entries.append(record)
        except OSError:
            return []
    return entries


def summarize_usage(*, window_days: int = 14) -> Dict[str, object]:
    """Aggregate preset launches within the supplied window."""

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=max(window_days, 1))
    entries = [entry for entry in _load_entries() if entry.timestamp >= cutoff]
    total_count = len(entries)

    preset_name_lookup = {preset.id: preset.name for preset in PRESETS}
    bundle_label_lookup = {preset.bundle: preset.bundle_label for preset in PRESETS if preset.bundle}

    preset_counter: Counter[str] = Counter()
    bundle_counter: Counter[str] = Counter()
    plan_counter: Counter[str] = Counter()
    preset_channels: Dict[str, Counter[str]] = {}
    preset_last_used: Dict[str, datetime] = {}
    preset_bundle_map: Dict[str, str] = {}

    for entry in entries:
        preset_counter[entry.preset_id] += 1
        if entry.bundle:
            bundle_counter[entry.bundle] += 1
            preset_bundle_map[entry.preset_id] = entry.bundle
        if entry.plan_tier:
            plan_counter[entry.plan_tier] += 1
        channel_counter = preset_channels.setdefault(entry.preset_id, Counter())
        for channel in entry.channel_types:
            channel_counter[channel] += 1
        preset_last_used[entry.preset_id] = max(
            entry.timestamp, preset_last_used.get(entry.preset_id, entry.timestamp)
        )

    preset_items = []
    for preset_id, count in preset_counter.most_common():
        preset_items.append(
            {
                "presetId": preset_id,
                "name": preset_name_lookup.get(preset_id),
                "bundle": preset_bundle_map.get(preset_id),
                "bundleLabel": bundle_label_lookup.get(preset_bundle_map.get(preset_id)),
                "count": count,
                "lastUsedAt": preset_last_used.get(preset_id).isoformat() if preset_last_used.get(preset_id) else None,
                "channelTotals": dict(preset_channels.get(preset_id, {})),
            }
        )

    bundle_items = [
        {"bundle": bundle, "label": bundle_label_lookup.get(bundle), "count": count}
        for bundle, count in bundle_counter.most_common()
    ]

    return {
        "generatedAt": now.isoformat(),
        "windowDays": window_days,
        "totalLaunches": total_count,
        "presets": preset_items,
        "bundles": bundle_items,
        "planTotals": dict(plan_counter),
    }


__all__ = ["record_usage", "summarize_usage"]
