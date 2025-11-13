"""Compile alert rule DSL into structured execution plans."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
import shlex
from typing import Any, List, Mapping, MutableMapping, Optional, Sequence, Tuple

from core.logging import get_logger

logger = get_logger(__name__)

_WINDOW_RE = re.compile(r"^(?P<value>\d+)(?P<unit>[smhdw])$", re.IGNORECASE)
_SENTIMENT_RE = re.compile(r"^(?P<field>sentiment|minsentiment)(?P<op>>=|<=|>|<|=)(?P<value>-?\d+(\.\d+)?)$", re.IGNORECASE)
_DEFAULT_SOURCE = "filing"
_MIN_WINDOW_MINUTES = 5
_MAX_WINDOW_MINUTES = 7 * 24 * 60


@dataclass(frozen=True)
class CompiledRulePlan:
    """Normalized representation of an alert rule."""

    source: str
    window_minutes: int
    tickers: Tuple[str, ...]
    categories: Tuple[str, ...]
    sectors: Tuple[str, ...]
    keywords: Tuple[str, ...]
    entities: Tuple[str, ...]
    min_sentiment: Optional[float] = None
    raw_dsl: Optional[str] = None

    def as_filters(self) -> Mapping[str, Any]:
        """Expose plan fields as dictionaries useful for downstream filters."""

        return {
            "source": self.source,
            "windowMinutes": self.window_minutes,
            "tickers": list(self.tickers),
            "categories": list(self.categories),
            "sectors": list(self.sectors),
            "keywords": list(self.keywords),
            "entities": list(self.entities),
            "minSentiment": self.min_sentiment,
            "dsl": self.raw_dsl,
        }


def compile_trigger(
    trigger: Optional[Mapping[str, Any]],
    *,
    default_window_minutes: int,
    default_source: str = _DEFAULT_SOURCE,
) -> CompiledRulePlan:
    """Compile trigger payload (DSL-aware) into a :class:`CompiledRulePlan`."""

    payload: Mapping[str, Any] = trigger or {}
    dsl_text = _coerce_str(payload.get("dsl") or payload.get("query") or payload.get("expression"))
    structured = _extract_structured_fields(payload, default_source=default_source)
    dsl_fields = _parse_dsl(dsl_text) if dsl_text else {}

    plan_source = dsl_fields.get("source") or structured["source"] or default_source
    window_minutes = dsl_fields.get("window_minutes") or structured.get("window_minutes") or default_window_minutes
    window_minutes = _clamp_window_minutes(window_minutes or default_window_minutes)

    tickers = _merge_lists(structured.get("tickers"), dsl_fields.get("tickers"))
    categories = _merge_lists(structured.get("categories"), dsl_fields.get("categories"))
    sectors = _merge_lists(structured.get("sectors"), dsl_fields.get("sectors"))
    keywords = _merge_lists(structured.get("keywords"), dsl_fields.get("keywords"))
    entities = _merge_lists(structured.get("entities"), dsl_fields.get("entities"))

    min_sentiment = dsl_fields.get("min_sentiment")
    if min_sentiment is None and structured.get("min_sentiment") is not None:
        min_sentiment = structured["min_sentiment"]

    return CompiledRulePlan(
        source=plan_source,
        window_minutes=window_minutes,
        tickers=tuple(tickers),
        categories=tuple(categories),
        sectors=tuple(sectors),
        keywords=tuple(keywords),
        entities=tuple(entities),
        min_sentiment=min_sentiment,
        raw_dsl=dsl_text,
    )


def plan_signature(plan: CompiledRulePlan) -> str:
    """Stable hash representing the significant filters for a rule."""

    payload = {
        "source": plan.source,
        "window_minutes": plan.window_minutes,
        "tickers": list(plan.tickers),
        "categories": list(plan.categories),
        "sectors": list(plan.sectors),
        "keywords": list(plan.keywords),
        "entities": list(plan.entities),
        "min_sentiment": plan.min_sentiment,
    }
    serialized = json.dumps(payload, separators=(",", ":"), sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def snapshot_digest(events: Sequence[Mapping[str, Any]]) -> str:
    """Return a deterministic hash for a batch of alert events."""

    normalized = [json.dumps(event, sort_keys=True, separators=(",", ":")) for event in events]
    serialized = json.dumps(sorted(normalized), separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _extract_structured_fields(
    payload: Mapping[str, Any],
    *,
    default_source: str,
) -> MutableMapping[str, Any]:
    source = _coerce_str(payload.get("type")) or default_source
    tickers = _normalize_list(payload.get("tickers"))
    categories = _normalize_list(payload.get("categories"))
    sectors = _normalize_list(payload.get("sectors"))
    keywords = _normalize_list(payload.get("keywords"))
    entities = _normalize_list(payload.get("entities"))
    min_sentiment = _coerce_float(payload.get("minSentiment"))
    window_minutes = _coerce_int(payload.get("windowMinutes"))

    return {
        "source": source,
        "tickers": tickers,
        "categories": categories,
        "sectors": sectors,
        "keywords": keywords,
        "entities": entities,
        "min_sentiment": min_sentiment,
        "window_minutes": window_minutes,
    }


def _parse_dsl(text: str) -> MutableMapping[str, Any]:
    tokens = _tokenize(text)
    result: MutableMapping[str, Any] = {
        "source": None,
        "tickers": [],
        "categories": [],
        "sectors": [],
        "keywords": [],
        "entities": [],
        "window_minutes": None,
        "min_sentiment": None,
    }

    for token in tokens:
        if not token:
            continue
        lower = token.lower()
        if lower in {"news", "filing"}:
            result["source"] = lower
            continue
        match = _SENTIMENT_RE.match(lower)
        if match:
            result["min_sentiment"] = float(match.group("value"))
            continue
        if ":" in token:
            key, raw_value = token.split(":", 1)
            key = key.strip().lower()
            value = raw_value.strip()
            _apply_keyed_clause(result, key, value)
            continue
        # Bare tokens are treated as keyword filters.
        result["keywords"].append(token)

    return result


def _apply_keyed_clause(result: MutableMapping[str, Any], key: str, value: str) -> None:
    cleaned_value = _strip_wrapping(value)
    if key in {"ticker", "tickers"}:
        result["tickers"].extend(_split_multi(cleaned_value))
    elif key in {"keyword", "keywords"}:
        result["keywords"].extend(_split_multi(cleaned_value))
    elif key in {"entity", "entities"}:
        result["entities"].extend(_split_multi(cleaned_value))
    elif key in {"category", "categories"}:
        result["categories"].extend(_split_multi(cleaned_value))
    elif key in {"sector", "sectors"}:
        result["sectors"].extend(_split_multi(cleaned_value))
    elif key in {"window", "window_minutes", "windowmins"}:
        window = _parse_window_expression(cleaned_value)
        if window is not None:
            result["window_minutes"] = window
    elif key in {"type", "source"} and cleaned_value:
        lowered = cleaned_value.lower()
        if lowered in {"news", "filing"}:
            result["source"] = lowered
    elif key in {"sentiment", "minsentiment"}:
        value_float = _coerce_float(cleaned_value)
        if value_float is not None:
            result["min_sentiment"] = value_float
    else:
        logger.debug("Unhandled DSL key '%s' (value=%s)", key, value)


def _tokenize(text: str) -> List[str]:
    try:
        return shlex.split(text)
    except ValueError:
        # Fall back to naive split if quoting is broken.
        return text.split()


def _split_multi(value: str) -> List[str]:
    if not value:
        return []
    if value.startswith("(") and value.endswith(")"):
        value = value[1:-1]
    parts = re.split(r"[,\|]", value)
    normalized: List[str] = []
    for part in parts:
        stripped = part.strip()
        if stripped:
            normalized.append(stripped)
    return normalized


def _strip_wrapping(value: str) -> str:
    stripped = value.strip()
    if len(stripped) >= 2 and stripped[0] == stripped[-1] and stripped[0] in {"'", '"'}:
        return stripped[1:-1]
    return stripped


def _parse_window_expression(value: str) -> Optional[int]:
    if not value:
        return None
    match = _WINDOW_RE.match(value)
    if match:
        number = int(match.group("value"))
        unit = match.group("unit").lower()
        if unit == "s":
            return max(number // 60, 1)
        if unit == "m":
            return number
        if unit == "h":
            return number * 60
        if unit == "d":
            return number * 60 * 24
        if unit == "w":
            return number * 60 * 24 * 7
    # Plain integer minutes.
    candidate = _coerce_int(value)
    if candidate is not None:
        return candidate
    logger.debug("Unable to parse window expression '%s'", value)
    return None


def _merge_lists(lhs: Optional[Sequence[str]], rhs: Optional[Sequence[str]]) -> List[str]:
    seen = set()
    merged: List[str] = []
    for source in (lhs or []), (rhs or []):
        for item in source:
            normalized = item.strip()
            if not normalized:
                continue
            if normalized not in seen:
                merged.append(normalized)
                seen.add(normalized)
    return merged


def _normalize_list(values: Any) -> List[str]:
    if not values:
        return []
    if isinstance(values, str):
        return [values.strip()] if values.strip() else []
    normalized: List[str] = []
    for value in values:
        if not isinstance(value, str):
            continue
        stripped = value.strip()
        if stripped:
            normalized.append(stripped)
    return normalized


def _coerce_str(value: Any) -> Optional[str]:
    if value in (None, "", False):
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return str(value)


def _coerce_int(value: Any) -> Optional[int]:
    if value in (None, "", False):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_float(value: Any) -> Optional[float]:
    if value in (None, "", False):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _clamp_window_minutes(value: int) -> int:
    return max(_MIN_WINDOW_MINUTES, min(value, _MAX_WINDOW_MINUTES))


__all__ = [
    "CompiledRulePlan",
    "compile_trigger",
    "plan_signature",
    "snapshot_digest",
]
