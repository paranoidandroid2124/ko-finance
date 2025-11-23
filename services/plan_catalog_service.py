"""Persistence helpers for plan tier catalog messaging."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

from core.logging import get_logger
from services.json_store import JsonStore
from core.plan_constants import SUPPORTED_PLAN_TIERS
from datetime import datetime, timezone

DEFAULT_PLAN_CATALOG_PATH = Path("uploads") / "admin" / "plan_catalog.json"

logger = get_logger(__name__)
_PLAN_CATALOG_STORE = JsonStore(
    path_env="PLAN_CATALOG_FILE",
    default_path=DEFAULT_PLAN_CATALOG_PATH,
)


class PlanCatalogConflictError(RuntimeError):
    """Raised when concurrent updates modify the plan catalog."""

    def __init__(self, message: str = "다른 사용자가 플랜 카탈로그를 먼저 수정했습니다. 새로고침 후 다시 시도해주세요.") -> None:
        super().__init__(message)

_DEFAULT_TIER_CARDS: List[Dict[str, Any]] = [
    {
        "tier": "free",
        "title": "무료로 시작하는 리서치 파이프라인",
        "tagline": "기업 뉴스와 공시를 한곳에 모으고 RAG 워크플로를 가볍게 체험해 보세요.",
        "badge": "Free",
        "price": {"amount": 0, "currency": "KRW", "interval": "월"},
        "ctaLabel": "무료로 시작하기",
        "ctaHref": "/auth/register?plan=free",
        "features": [
            {"text": "AI를 통한 공시 분석"},
            {"text": "공시·뉴스·요약 기본 피드 열람"},
            {"text": "감성 지표와 리포트 샘플 미리 보기"},
            {"text": "간단한 PDF 다운로드 및 공유"},
        ],
        "imageUrl": None,
        "supportNote": "셀프 온보딩 가이드를 제공합니다",
    },
    {
        "tier": "starter",
        "title": "Starter · 경량 리서치 자동화",
        "tagline": "워치리스트·알림·근거 스니펫까지 하루 업무 흐름을 자동화합니다.",
        "badge": "Starter",
        "price": {"amount": 9900, "currency": "KRW", "interval": "월", "note": "VAT 별도"},
        "ctaLabel": "Starter 업그레이드",
        "ctaHref": "/checkout?plan=starter",
        "features": [
            {"text": "워치리스트 50 · 알림 룰 10개", "highlight": True},
            {"text": "하루 80회 RAG 질문과 증거 링크"},
            {"text": "PDF 하이라이트 · 요약 스니펫 저장"},
            {"text": "Starter 30일 Pro 체험 쿠폰 포함"},
        ],
        "imageUrl": None,
        "supportNote": "이메일 지원 · 알림 템플릿 제공",
    },
    {
        "tier": "pro",
        "title": "파일럿 협업을 위한 Pro",
        "tagline": "워치리스트 알림과 비교 분석을 연계해 팀 업무에 바로 적용하세요.",
        "badge": "Best",
        "price": {"amount": 14900, "currency": "KRW", "interval": "월", "note": "부가세 포함"},
        "ctaLabel": "Pro 구독하기",
        "ctaHref": "/checkout?plan=pro",
        "features": [
            {"text": "확장된 AI 대화 기능", "highlight": True},
            {"text": "워치리스트 자동 알림(Slack/Email)"},
            {"text": "기업 비교 검색과 인라인 PDF 뷰어"},
            {"text": "맞춤 다이제스트와 운영 리포트 자동 발송"},
        ],
        "imageUrl": None,
        "supportNote": "전담 고객 성공 매니저 배정",
    },
    {
        "tier": "enterprise",
        "title": "엔터프라이즈 전용 패키지",
        "tagline": "감사·보안 요건을 충족하고 전사 워크플로를 맞춤 구성하세요.",
        "badge": "Premium",
        "price": {"amount": 49900, "currency": "KRW", "interval": "월", "note": "부가세 포함"},
        "ctaLabel": "담당자에게 문의",
        "ctaHref": "/contact?plan=enterprise",
        "features": [
            {"text": "차트·검색 무제한 · RAG Top-K 20", "highlight": True},
            {"text": "데이터 익스포트와 증거 Diff 비교"},
            {"text": "타임라인 풀 액세스 · 협업 워크스페이스"},
            {"text": "전담 컨설턴트 · 보안/감사 맞춤 지원"},
        ],
        "imageUrl": None,
        "supportNote": "보안·감사 자료 세트 포함",
    },

]


def _normalize_feature(feature: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    text = str(feature.get("text") or "").strip()
    if not text:
        return None
    highlight = bool(feature.get("highlight")) if feature.get("highlight") is not None else None
    icon = feature.get("icon")
    icon_value = str(icon).strip() if isinstance(icon, str) and icon.strip() else None
    return {"text": text, "highlight": highlight, "icon": icon_value}


def _normalize_price(raw: Dict[str, Any]) -> Dict[str, Any]:
    amount = raw.get("amount", 0)
    try:
        numeric_amount = float(amount)
    except (TypeError, ValueError):
        numeric_amount = 0.0
    currency = str(raw.get("currency") or "KRW").upper()
    interval = str(raw.get("interval") or "월").strip() or "월"
    note = raw.get("note")
    note_value = str(note).strip() if isinstance(note, str) and note.strip() else None
    return {
        "amount": numeric_amount,
        "currency": currency,
        "interval": interval,
        "note": note_value,
    }


def _normalize_tier(raw: Dict[str, Any]) -> Dict[str, Any]:
    tier = str(raw.get("tier") or "").strip().lower()
    if tier not in SUPPORTED_PLAN_TIERS:
        raise ValueError(f"Unsupported plan tier: {tier!r}")

    title = str(raw.get("title") or "").strip() or tier.title()
    tagline = str(raw.get("tagline") or "").strip()
    description = str(raw.get("description") or "").strip() or None
    badge = str(raw.get("badge") or "").strip() or None
    cta_label = str(raw.get("ctaLabel") or "").strip() or "자세히 보기"
    cta_href = str(raw.get("ctaHref") or "").strip() or "#"
    image_url = str(raw.get("imageUrl") or "").strip() or None
    support_note = str(raw.get("supportNote") or "").strip() or None

    price_raw = raw.get("price") or {}
    if not isinstance(price_raw, dict):
        price_raw = {}
    price = _normalize_price(price_raw)

    features_raw = raw.get("features") or []
    features: List[Dict[str, Any]] = []
    if isinstance(features_raw, Iterable):
        for item in features_raw:
            if not isinstance(item, dict):
                item = {"text": str(item)}
            normalized = _normalize_feature(item)
            if normalized:
                features.append(normalized)

    if not features:
        features = [{"text": "주요 기능을 곧 안내해 드릴게요."}]

    return {
        "tier": tier,
        "title": title,
        "tagline": tagline,
        "description": description,
        "badge": badge,
        "price": price,
        "ctaLabel": cta_label,
        "ctaHref": cta_href,
        "features": features,
        "imageUrl": image_url,
        "supportNote": support_note,
    }


def _default_catalog() -> Dict[str, Any]:
    return {
        "tiers": deepcopy(_DEFAULT_TIER_CARDS),
        "updated_at": None,
        "updated_by": None,
        "note": None,
    }


def _catalog_error_hook(path: Path, exc: Exception) -> None:
    logger.warning("Plan catalog load failed for %s: %s", path, exc)


def _load_catalog_from_raw(raw: Any) -> Dict[str, Any]:
    if not isinstance(raw, Mapping):
        raise ValueError("Plan catalog must be a JSON object.")

    tiers_raw = raw.get("tiers")
    normalized: List[Dict[str, Any]] = []
    if isinstance(tiers_raw, list):
        for entry in tiers_raw:
            try:
                normalized.append(_normalize_tier(entry or {}))
            except ValueError:
                continue
    if not normalized:
        normalized = deepcopy(_DEFAULT_TIER_CARDS)
    return {
        "tiers": normalized,
        "updated_at": raw.get("updated_at"),
        "updated_by": raw.get("updated_by"),
        "note": raw.get("note"),
    }


def load_plan_catalog(*, reload: bool = False) -> Dict[str, Any]:
    return _PLAN_CATALOG_STORE.load(
        loader=_load_catalog_from_raw,
        fallback=_default_catalog,
        reload=reload,
        on_error=_catalog_error_hook,
    )


def update_plan_catalog(
    tiers: Iterable[Dict[str, Any]],
    *,
    updated_by: Optional[str],
    note: Optional[str],
    expected_updated_at: Optional[str] = None,
) -> Dict[str, Any]:
    normalized_tiers: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for entry in tiers:
        parsed = _normalize_tier(entry or {})
        if parsed["tier"] in seen:
            continue
        normalized_tiers.append(parsed)
        seen.add(parsed["tier"])

    if not normalized_tiers:
        normalized_tiers = deepcopy(_DEFAULT_TIER_CARDS)

    current_state = load_plan_catalog(reload=True)
    current_updated_at = current_state.get("updated_at") if isinstance(current_state, dict) else None
    if expected_updated_at is not None and current_updated_at != expected_updated_at:
        raise PlanCatalogConflictError()

    payload = {
        "tiers": normalized_tiers,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "updated_by": (updated_by or "").strip() or None,
        "note": (note or "").strip() or None,
    }

    _PLAN_CATALOG_STORE.save(payload)

    return deepcopy(payload)


__all__ = ["PlanCatalogConflictError", "load_plan_catalog", "update_plan_catalog"]
