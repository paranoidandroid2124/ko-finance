"""Rule-based extractor for DART event metadata with YAML-configurable domains."""

from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Pattern, Sequence

import yaml

from core.env import env_bool
from models.filing import Filing

logger = logging.getLogger(__name__)
_STRICT_ANY_MATCH = env_bool("EVENT_EXTRACTOR_REQUIRE_ANY_MATCH", False)
_DEFAULT_RULE_PATH = Path("configs") / "event_rules.yaml"
_DEFAULT_DOMAIN = "FIN"


@dataclass
class EventAttributes:
    event_type: Optional[str]
    amount: Optional[float]
    ratio: Optional[float]
    method: Optional[str]
    score: float
    is_negative: bool = False
    domain: Optional[str] = None
    subtype: Optional[str] = None
    timing_rule: str = "AUTO"
    confidence: float = 0.0
    is_restatement: bool = False
    matches: Dict[str, Sequence[str]] = field(default_factory=dict)


@dataclass
class Rule:
    name: str
    domain: str = _DEFAULT_DOMAIN
    require_all: Sequence[str] = field(default_factory=list)
    any_of: Sequence[str] = field(default_factory=list)
    exclude: Sequence[str] = field(default_factory=list)
    subtype_map: Dict[str, str] = field(default_factory=dict)
    method_map: Dict[str, str] = field(default_factory=dict)
    timing_rule: str = "AUTO"
    acts_as_modifier: bool = False

    require_all_compiled: Sequence[Pattern[str]] = field(default_factory=list, init=False)
    any_of_compiled: Sequence[Pattern[str]] = field(default_factory=list, init=False)
    exclude_compiled: Sequence[Pattern[str]] = field(default_factory=list, init=False)
    subtype_map_compiled: Dict[str, Pattern[str]] = field(default_factory=dict, init=False)
    method_map_compiled: Dict[str, Pattern[str]] = field(default_factory=dict, init=False)

    def compile(self, prefix: str = "") -> Rule:
        def _compile(pattern: str) -> Pattern[str]:
            candidate = pattern
            if prefix and not candidate.startswith(prefix):
                candidate = f"{prefix}(?:{candidate})"
            return re.compile(candidate)

        self.require_all_compiled = [_compile(pattern) for pattern in self.require_all]
        self.any_of_compiled = [_compile(pattern) for pattern in self.any_of]
        self.exclude_compiled = [_compile(pattern) for pattern in self.exclude]
        self.subtype_map_compiled = {key: _compile(expr) for key, expr in self.subtype_map.items()}
        self.method_map_compiled = {key: _compile(expr) for key, expr in self.method_map.items()}
        return self


def _load_event_rules(path: Path = _DEFAULT_RULE_PATH) -> Optional[List[Rule]]:
    if not path.exists():
        logger.info("event rule config not found at %s; falling back to legacy rules", path)
        return None

    with path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle) or {}

    defaults = config.get("defaults") or {}
    pattern_prefix = defaults.get("flags", "")
    raw_rules = config.get("rules") or {}

    rules: List[Rule] = []
    for name, spec in raw_rules.items():
        merged = {
            "name": name,
            "domain": spec.get("domain", _DEFAULT_DOMAIN),
            "require_all": spec.get("require_all", []),
            "any_of": spec.get("any_of", []),
            "exclude": spec.get("exclude", []),
            "subtype_map": spec.get("subtype_map", {}),
            "method_map": spec.get("method_map", {}),
            "timing_rule": spec.get("timing_rule", "AUTO"),
            "acts_as_modifier": spec.get("acts_as_modifier", False),
        }
        rules.append(Rule(**merged).compile(pattern_prefix))

    priority = config.get("priority") or []
    priority_index = {domain: idx for idx, domain in enumerate(priority)}
    rules.sort(key=lambda rule: priority_index.get(rule.domain, len(priority_index)))
    logger.info("loaded %d event extraction rules from %s", len(rules), path)
    return rules


_EVENT_RULES = _load_event_rules()
_RULE_INDEX: Dict[str, Rule] = {rule.name: rule for rule in _EVENT_RULES or []}

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
        "any": ("발행", "리픽싱", "전환가격", "청구"),
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

_METHOD_KEYWORDS = {
    "주주배정": "rights",
    "제3자배정": "private",
    "일반공모": "public",
    "공모": "public",
    "사모": "private",
    "시장매수": "open_market",
    "시장외매수": "off_market",
    "시장외대량매매": "off_market",
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

_NEGATIVE_KEYWORDS = ("해지", "취소", "철회", "무산", "중단", "연장", "종료")


def extract_event_attributes(filing: Filing) -> EventAttributes:
    """Return structured attributes for downstream event study ingestion."""

    haystack = _build_haystack(filing)
    if _EVENT_RULES:
        return _extract_with_config(haystack)
    return _extract_with_legacy(haystack)


def get_event_rule_metadata(event_type: str) -> Optional[Dict[str, str]]:
    rule = _RULE_INDEX.get(event_type)
    if not rule:
        return None
    return {"domain": rule.domain, "timing_rule": rule.timing_rule}


def _extract_with_config(text: str) -> EventAttributes:
    text_lower = text.lower()
    amount = _extract_amount(text)
    ratio = _extract_ratio(text)
    method = _extract_method(text)  # fallback if rule has no method_map hit
    is_negative = any(keyword in text_lower for keyword in _NEGATIVE_KEYWORDS)

    event_type: Optional[str] = None
    domain: Optional[str] = None
    subtype: Optional[str] = None
    timing_rule = "AUTO"
    confidence = 0.0
    is_restatement = False
    matches: Dict[str, Sequence[str]] = {}

    for rule in _EVENT_RULES or []:
        req_ok, req_hits = _match_all(text, rule.require_all_compiled)
        any_ok, any_hits = _match_any(text, rule.any_of_compiled)
        exc_ok = _match_none(text, rule.exclude_compiled)
        if not req_ok or not any_ok or not exc_ok:
            continue

        if rule.acts_as_modifier:
            is_restatement = True
            continue

        event_type = rule.name
        domain = rule.domain
        timing_rule = rule.timing_rule
        matches = {"require": req_hits, "any": any_hits}

        for key, pattern in rule.subtype_map_compiled.items():
            if pattern.search(text):
                subtype = key
                break

        method_override = None
        for key, pattern in rule.method_map_compiled.items():
            if pattern.search(text):
                method_override = key
                break
        if method_override:
            method = method_override.lower()

        confidence = _compute_confidence(text, subtype, method)
        break

    domain = domain or _DEFAULT_DOMAIN
    score = _compute_salience(event_type, amount, ratio, is_negative=is_negative)
    return EventAttributes(
        event_type=event_type,
        amount=amount,
        ratio=ratio,
        method=method,
        score=score,
        is_negative=is_negative,
        domain=domain,
        subtype=subtype,
        timing_rule=timing_rule,
        confidence=confidence,
        is_restatement=is_restatement,
        matches=matches,
    )


def _extract_with_legacy(text: str) -> EventAttributes:
    text_lower = text.lower()
    event_type = _classify_event_type(text_lower)
    amount = _extract_amount(text)
    ratio = _extract_ratio(text)
    method = _extract_method(text)
    is_negative = any(keyword in text_lower for keyword in _NEGATIVE_KEYWORDS)
    score = _compute_salience(event_type, amount, ratio, is_negative=is_negative)
    confidence = _compute_confidence(text, None, method)

    return EventAttributes(
        event_type=event_type,
        amount=amount,
        ratio=ratio,
        method=method,
        score=score,
        is_negative=is_negative,
        domain=_DEFAULT_DOMAIN,
        confidence=confidence,
    )


def _match_all(text: str, patterns: Sequence[Pattern[str]]) -> tuple[bool, List[str]]:
    hits: List[str] = []
    for pattern in patterns:
        match = pattern.search(text)
        if not match:
            return False, []
        hits.append(match.group(0))
    return True, hits


def _match_any(text: str, patterns: Sequence[Pattern[str]]) -> tuple[bool, List[str]]:
    if not patterns:
        return True, []
    hits = [match.group(0) for pattern in patterns if (match := pattern.search(text))]
    return (True, hits) if hits else (False, [])


def _match_none(text: str, patterns: Sequence[Pattern[str]]) -> bool:
    return all(pattern.search(text) is None for pattern in patterns)


def _build_haystack(filing: Filing) -> str:
    sources = [
        filing.report_name,
        filing.title,
        getattr(filing, "raw_md", None),
        getattr(filing, "notes", None),
    ]
    filtered = [part.strip() for part in sources if part and isinstance(part, str)]
    return " ".join(filtered) if filtered else ""


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
            logger.debug("Relaxed event match for %s", rule.get("type", "UNKNOWN"))
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


def _compute_confidence(text: str, subtype: Optional[str], method: Optional[str]) -> float:
    has_amount = bool(_AMOUNT_PATTERN.search(text))
    has_term = bool(re.search(r"(기간|기일|만기|~|\d+\s*(일|개월|년))", text))
    points = 0.4 * has_amount + 0.2 * has_term
    if subtype:
        points += 0.2
    if method:
        points += 0.2
    return round(min(1.0, 0.2 + points), 2)


def _compute_salience(
    event_type: Optional[str],
    amount: Optional[float],
    ratio: Optional[float],
    *,
    is_negative: bool,
) -> float:
    """Heuristic score in [0, 1] prioritising large or rare events."""

    base = {
        "BUYBACK": 0.6,
        "BUYBACK_DISPOSAL": 0.45,
        "SEO": 0.5,
        "DIVIDEND": 0.55,
        "RESTATEMENT": 0.5,
        "CONTRACT": 0.5,
        "CONTRACT_TERMINATION": 0.5,
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


__all__ = ["EventAttributes", "extract_event_attributes", "get_event_rule_metadata"]
