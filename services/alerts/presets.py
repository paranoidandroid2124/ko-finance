"""Preset definitions for alert bundles."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Sequence


@dataclass(frozen=True)
class AlertPresetDefinition:
    """Static descriptor for a recommended alert rule."""

    id: str
    bundle: str
    bundle_label: str
    plan_tiers: Sequence[str]
    name: str
    description: str
    tags: Sequence[str] = field(default_factory=tuple)
    sample_dsl: str | None = None
    trigger: Mapping[str, Any] = field(default_factory=dict)
    frequency: Mapping[str, Any] = field(default_factory=dict)
    recommended_channel: str = "email"
    insight: str | None = None
    priority: int = 0

    def applies_to(self, plan_tier: str) -> bool:
        normalized = plan_tier or ""
        if normalized in self.plan_tiers:
            return True
        if normalized == "enterprise":
            # Enterprise should inherit pro presets automatically.
            return "pro" in self.plan_tiers
        return False

    def to_payload(self) -> Dict[str, Any]:
        payload: MutableMapping[str, Any] = {
            "id": self.id,
            "bundle": self.bundle,
            "bundleLabel": self.bundle_label,
            "planTiers": list(self.plan_tiers),
            "name": self.name,
            "description": self.description,
            "tags": list(self.tags),
            "recommendedChannel": self.recommended_channel,
            "trigger": dict(self.trigger),
            "frequency": dict(self.frequency),
            "priority": self.priority,
        }
        if self.sample_dsl:
            payload["sampleDsl"] = self.sample_dsl
        if self.insight:
            payload["insight"] = self.insight
        return dict(payload)


def _definition(
    *,
    id: str,
    bundle: str,
    bundle_label: str,
    plan_tiers: Sequence[str],
    name: str,
    description: str,
    tags: Iterable[str],
    sample_dsl: str,
    trigger: Mapping[str, Any],
    frequency: Mapping[str, Any],
    recommended_channel: str = "email",
    insight: str | None = None,
    priority: int = 0,
) -> AlertPresetDefinition:
    return AlertPresetDefinition(
        id=id,
        bundle=bundle,
        bundle_label=bundle_label,
        plan_tiers=tuple(plan_tiers),
        name=name,
        description=description,
        tags=tuple(tags),
        sample_dsl=sample_dsl,
        trigger=trigger,
        frequency=frequency,
        recommended_channel=recommended_channel,
        insight=insight,
        priority=priority,
    )


PRESETS: Sequence[AlertPresetDefinition] = (
    _definition(
        id="starter_buyback_radar",
        bundle="starter",
        bundle_label="Starter 기본 세트",
        plan_tiers=("starter", "pro"),
        name="자사주 매입 · 소각 공시",
        description="대형주 자사주 매입/소각 결정 공시를 6시간 윈도우로 포착합니다.",
        tags=("공시", "Buyback"),
        sample_dsl="filing keyword:'자사주' keyword:'소각' window:6h",
        trigger={
            "type": "filing",
            "tickers": [],
            "categories": [],
            "sectors": [],
            "keywords": ["자사주", "자기주식", "소각"],
            "entities": [],
            "dsl": "filing keyword:'자사주' keyword:'소각' window:6h",
        },
        frequency={
            "evaluationIntervalMinutes": 30,
            "windowMinutes": 360,
            "cooldownMinutes": 120,
            "maxTriggersPerDay": 12,
        },
        recommended_channel="email",
        insight="주가 부양 이슈를 놓치지 않도록 Starter 플랜에서 가장 많이 쓰는 조합입니다.",
        priority=10,
    ),
    _definition(
        id="starter_dilution_guard",
        bundle="starter",
        bundle_label="Starter 기본 세트",
        plan_tiers=("starter", "pro"),
        name="희석/증자 공시 안전망",
        description="유상증자 · CB/EB 발행과 같이 희석 가능성이 있는 공시를 하루 1회 묶어줍니다.",
        tags=("공시", "리스크"),
        sample_dsl="filing keyword:'유상증자' keyword:'전환사채' window:12h",
        trigger={
            "type": "filing",
            "tickers": [],
            "categories": [],
            "sectors": [],
            "keywords": ["유상증자", "전환사채", "신주발행", "BW"],
            "entities": [],
            "dsl": "filing keyword:'유상증자' keyword:'전환사채' window:12h",
        },
        frequency={
            "evaluationIntervalMinutes": 45,
            "windowMinutes": 720,
            "cooldownMinutes": 240,
            "maxTriggersPerDay": 6,
        },
        recommended_channel="email",
        insight="IR/전략팀이 매일 아침 확인하는 희석 리스크 요약.",
        priority=9,
    ),
    _definition(
        id="starter_watchlist_radar",
        bundle="starter",
        bundle_label="Starter Digest",
        plan_tiers=("starter", "pro"),
        name="워치리스트 데일리 다이제스트",
        description="전일 워치리스트 알림을 묶어 이메일/Slack으로 받아볼 수 있는 프리셋입니다.",
        tags=("Digest", "Watchlist"),
        sample_dsl="news watchlist:true window:24h",
        trigger={
            "type": "news",
            "tickers": [],
            "categories": [],
            "sectors": [],
            "keywords": [],
            "entities": [],
            "minSentiment": None,
            "dsl": "news watchlist:true window:24h",
        },
        frequency={
            "evaluationIntervalMinutes": 60,
            "windowMinutes": 1440,
            "cooldownMinutes": 720,
            "maxTriggersPerDay": 1,
        },
        recommended_channel="email",
        insight="Starter 사용자가 Digest 온보딩용으로 가장 빨리 구성할 수 있는 조합.",
        priority=8,
    ),
    _definition(
        id="pro_earnings_spike",
        bundle="pro",
        bundle_label="Pro 이벤트 스캐너",
        plan_tiers=("pro",),
        name="잠정실적/어닝 서프라이즈",
        description="잠정실적/어닝 키워드와 영업이익 언급을 3시간 단위로 모니터링합니다.",
        tags=("공시", "실적"),
        sample_dsl="filing keyword:'잠정실적' keyword:'영업이익' window:3h",
        trigger={
            "type": "filing",
            "tickers": [],
            "categories": [],
            "sectors": [],
            "keywords": ["잠정실적", "영업이익", "어닝"],
            "entities": [],
            "dsl": "filing keyword:'잠정실적' keyword:'영업이익' window:3h",
        },
        frequency={
            "evaluationIntervalMinutes": 10,
            "windowMinutes": 180,
            "cooldownMinutes": 60,
            "maxTriggersPerDay": 24,
        },
        recommended_channel="telegram",
        insight="Pro 리서처가 실적 관련 공시를 장중에 바로 받기 위한 파라미터.",
        priority=7,
    ),
    _definition(
        id="pro_negative_news_sentry",
        bundle="pro",
        bundle_label="Pro 이벤트 스캐너",
        plan_tiers=("pro",),
        name="부정 뉴스 감시",
        description="리콜/소송/제재 등 부정 키워드가 포함된 뉴스 및 감성 ≤ -0.3 신호를 잡습니다.",
        tags=("뉴스", "Sentiment"),
        sample_dsl="news keyword:'소송' keyword:'리콜' sentiment<=-0.3 window:90m",
        trigger={
            "type": "news",
            "tickers": [],
            "categories": [],
            "sectors": [],
            "keywords": ["소송", "리콜", "제재", "리스크"],
            "entities": [],
            "minSentiment": -0.3,
            "dsl": "news keyword:'소송' keyword:'리콜' sentiment<=-0.3 window:90m",
        },
        frequency={
            "evaluationIntervalMinutes": 15,
            "windowMinutes": 90,
            "cooldownMinutes": 45,
            "maxTriggersPerDay": 36,
        },
        recommended_channel="slack",
        insight="부정 감성 뉴스가 몰릴 때 Slack 룸으로 바로 공유하기 위한 조합.",
        priority=6,
    ),
    _definition(
        id="pro_mna_heatmap",
        bundle="pro",
        bundle_label="Pro 이벤트 스캐너",
        plan_tiers=("pro",),
        name="대형 M&A/매각 이슈",
        description="인수합병/매각 공시 및 뉴스 키워드를 짧은 윈도우로 묶어줍니다.",
        tags=("M&A", "Deal"),
        sample_dsl="filing keyword:'인수' keyword:'매각' window:4h",
        trigger={
            "type": "filing",
            "tickers": [],
            "categories": [],
            "sectors": [],
            "keywords": ["인수", "합병", "매각", "M&A"],
            "entities": [],
            "dsl": "filing keyword:'인수' keyword:'매각' window:4h",
        },
        frequency={
            "evaluationIntervalMinutes": 20,
            "windowMinutes": 240,
            "cooldownMinutes": 90,
            "maxTriggersPerDay": 16,
        },
        recommended_channel="email",
        insight="전략/신사업팀이 딜 히트맵으로 쓰는 대표 프리셋.",
        priority=5,
    ),
)


def list_alert_presets(plan_tier: str) -> List[Dict[str, Any]]:
    """Return ordered preset payloads for the requested plan."""

    available = [preset for preset in PRESETS if preset.applies_to(plan_tier)]
    ordered = sorted(available, key=lambda preset: preset.priority, reverse=True)
    return [preset.to_payload() for preset in ordered]


__all__ = ["list_alert_presets", "AlertPresetDefinition"]
