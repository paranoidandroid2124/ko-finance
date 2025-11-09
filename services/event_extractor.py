"\"\"\"Rule-based extractor for DART event metadata.\"\"\""

from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass
from typing import Dict, Optional, Sequence

from core.env import env_bool
from models.filing import Filing


@dataclass
class EventAttributes:
    event_type: Optional[str]
    amount: Optional[float]
    ratio: Optional[float]
    method: Optional[str]
    score: float
    is_negative: bool = False


_TYPE_RULES = [
    {
        "type": "BUYBACK",
        "require": [("자사주", "자기주식")],
        "any": ("취득", "매입", "소각", "취득결정", "소각결정", "취득 예정"),
        "exclude": ("처분", "양도", "매각"),
    },
    {
        "type": "BUYBACK_DISPOSAL",
        "require": [("자사주", "자기주식")],
        "any": ("처분", "양도", "매각"),
    },
    {
        "type": "SEO",
        "require": [("유상증자", "증자", "신주발행", "신주모집")],
        "any": ("제3자배정", "주주배정", "일반공모", "청약", "납입"),
    },
    {
        "type": "DIVIDEND",
        "require": [("배당", "현금배당", "주식배당")],
        "any": ("배당금", "배당금총액", "1주당", "DPS", "배당기준일"),
    },
    {
        "type": "RESTATEMENT",
        "require": [("정정", "정정공시", "재작성", "착오")],
        "any": ("정정전", "정정후", "추가기재"),
    },
    {
        "type": "CONVERTIBLE",
        "require": [("전환사채", "교환사채", "신주인수권부사채", "CB", "BW", "EB")],
        "any": ("발행", "리픽싱", "전환가액", "청구", "콜옵션"),
    },
    {
        "type": "MNA",
        "require": [("합병", "분할", "영업양수", "영업양도", "주식양수", "주식양도")],
        "any": ("합병비율", "존속회사", "소멸회사", "분할기일"),
    },
    {
        "type": "CONTRACT",
        "require": [("공급계약", "단일판매", "단일공급", "수주", "계약체결")],
        "any": ("계약금액", "계약기간", "계약상대"),
    },
]

logger = logging.getLogger(__name__)
_STRICT_ANY_MATCH = env_bool("EVENT_EXTRACTOR_REQUIRE_ANY_MATCH", False)

_METHOD_KEYWORDS = {
    "주주배정": "rights",
    "제3자배정": "private",
    "일반공모": "public",
    "공모": "public",
    "사모": "private",
    "시장매수": "open_market",
    "시간외매수": "off_market",
    "시간외대량매매": "off_market",
    "맞교환": "swap",
    "장내매수": "open_market",
    "장외매수": "off_market",
    "처분": "disposal",
    "양도": "disposal",
}

_AMOUNT_PATTERN = re.compile(
    r"([0-9]+(?:[,.][0-9]+)?)\s*(조원|조|억원|억|백만원|백만|만원|만|원)",
    re.IGNORECASE,
)
_RATIO_PATTERN = re.compile(r"([+-]?[0-9]+(?:\.[0-9]+)?)\s*%", re.IGNORECASE)

_UNIT_MULTIPLIERS = {
    "조원": 1e12,
    "조": 1e12,
    "억원": 1e8,
    "억": 1e8,
    "백만원": 1e8 / 100,  # 1억 = 100백만
    "백만": 1e6,
    "만원": 1e4,
    "만": 1e4,
    "원": 1.0,
}


def extract_event_attributes(filing: Filing) -> EventAttributes:
    """Return structured attributes for downstream event study ingestion."""

    haystack = _build_haystack(filing)
    text_lower = haystack.lower()
    event_type = _classify_event_type(text_lower)
    amount = _extract_amount(haystack)
    ratio = _extract_ratio(haystack)
    method = _extract_method(haystack)
    is_negative = any(keyword in text_lower for keyword in _NEGATIVE_KEYWORDS)
    score = _compute_salience(event_type, amount, ratio, is_negative=is_negative)
    return EventAttributes(
        event_type=event_type,
        amount=amount,
        ratio=ratio,
        method=method,
        score=score,
        is_negative=is_negative,
    )


def _build_haystack(filing: Filing) -> str:
    sources = [
        filing.report_name,
        filing.title,
        getattr(filing, "raw_md", None),
        getattr(filing, "notes", None),
    ]
    filtered = [part.strip() for part in sources if part and isinstance(part, str)]
    if not filtered:
        return ""
    return " ".join(filtered)


def _classify_event_type(text: str) -> Optional[str]:
    for rule in _TYPE_RULES:
        if _match_rule(text, rule):
            return rule["type"]
    return None


def _match_rule(text: str, rule: Dict[str, Sequence[str]]) -> bool:
    require_groups = rule.get("require") or []
    for group in require_groups:
        if not any(keyword.lower() in text for keyword in group):
            return False
    any_keywords = rule.get("any") or ()
    any_matched = True
    if any_keywords:
        any_matched = any(keyword.lower() in text for keyword in any_keywords)
        if not any_matched and _STRICT_ANY_MATCH:
            return False
        if not any_matched and not _STRICT_ANY_MATCH:
            logger.debug(
                "Relaxed event match for %s (missing optional keywords).",
                rule.get("type", "UNKNOWN"),
            )
    exclude = rule.get("exclude") or []
    if any(keyword.lower() in text for keyword in exclude):
        return False
    return True


def _extract_amount(text: str) -> Optional[float]:
    matches = list(_AMOUNT_PATTERN.finditer(text))
    if not matches:
        return None
    values = []
    for match in matches:
        raw_value = match.group(1).replace(",", "")
        unit = match.group(2)
        try:
            base = float(raw_value)
        except ValueError:
            continue
        multiplier = _UNIT_MULTIPLIERS.get(unit.lower()) or _UNIT_MULTIPLIERS.get(unit)
        if multiplier is None:
            continue
        values.append(base * multiplier)

    if not values:
        return None
    # outline: pick the max magnitude as representative scale
    return max(values, key=abs)


def _extract_ratio(text: str) -> Optional[float]:
    match = _RATIO_PATTERN.search(text)
    if not match:
        return None
    try:
        value = float(match.group(1))
    except ValueError:
        return None
    return value / 100.0


def _extract_method(text: str) -> Optional[str]:
    for keyword, code in _METHOD_KEYWORDS.items():
        if keyword in text:
            return code
    return None


def _compute_salience(
    event_type: Optional[str],
    amount: Optional[float],
    ratio: Optional[float],
    *,
    is_negative: bool,
) -> float:
    """Heuristic score ∈ [0,1] prioritising large/rare events."""

    base = {
        "BUYBACK": 0.6,
        "BUYBACK_DISPOSAL": 0.45,
        "SEO": 0.5,
        "DIVIDEND": 0.55,
        "RESTATEMENT": 0.5,
        "CONTRACT": 0.5,
        "CONVERTIBLE": 0.45,
        "MNA": 0.65,
    }.get(event_type or "", 0.4)

    scale_component = 0.0
    if amount:
        scale_component = min(0.4, math.log10(abs(amount) + 1) / 12.0)
    ratio_component = 0.0
    if ratio:
        ratio_component = min(0.25, abs(ratio) * 2.0)
    penalty = 0.15 if is_negative else 0.0

    score = base + 0.35 * scale_component + 0.2 * ratio_component - penalty
    return max(0.05, min(0.99, score))


__all__ = ["EventAttributes", "extract_event_attributes"]
_NEGATIVE_KEYWORDS = ("해지", "취소", "철회", "무산", "중단", "연장", "종료")
