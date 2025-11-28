"""Peer comparison helpers for Commander tools."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from statistics import mean
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
import threading

from sqlalchemy import asc, func
from sqlalchemy.orm import Session

from core.logging import get_logger
from database import SessionLocal
from models.event_study import Price
from models.security_metadata import SecurityMetadata
from services import value_chain_repository

logger = get_logger(__name__)

DEFAULT_PERIOD_DAYS = 30
MIN_DATA_POINTS = 10

PEER_FALLBACK_MAP: Dict[str, List[str]] = {
    "005930": ["000660", "006400", "068270", "069500"],  # Samsung -> SK hynix, Samsung SDI, Celltrion, KOSPI200 ETF
    "000660": ["005930", "006400", "069500"],
    "035420": ["035720", "066570", "096770"],  # NAVER -> Kakao, LG전자, SK이노
    "035720": ["035420", "034730", "005930"],
    "068270": ["207940", "005935", "051910"],
}

VALUE_CHAIN_MAP: Dict[str, Dict[str, List[Dict[str, str]]]] = {
    "005930": {
        "suppliers": [
            {"ticker": "DJSEMICHEM", "label": "동진쎄미켐"},
            {"ticker": "SOULBRAIN", "label": "솔브레인"},
            {"ticker": "003670", "label": "포스코퓨처엠"},
        ],
        "customers": [
            {"ticker": "AAPL", "label": "Apple"},
            {"ticker": "DELL", "label": "Dell"},
            {"ticker": "NVDA", "label": "NVIDIA"},
        ],
        "peers": [
            {"ticker": "000660", "label": "SK hynix"},
            {"ticker": "MU", "label": "Micron"},
            {"ticker": "TSM", "label": "TSMC"},
        ],
    },
    "000660": {
        "suppliers": [
            {"ticker": "SOLBRAIN", "label": "솔브레인"},
            {"ticker": "LXSEMICON", "label": "LX세미콘"},
        ],
        "customers": [
            {"ticker": "NVDA", "label": "NVIDIA"},
            {"ticker": "AMZN", "label": "AWS"},
        ],
        "peers": [
            {"ticker": "005930", "label": "Samsung Elec"},
            {"ticker": "MU", "label": "Micron"},
        ],
    },
}

VALUE_CHAIN_CACHE: Dict[str, Dict[str, List[Dict[str, str]]]] = dict(VALUE_CHAIN_MAP)


def _normalize_ticker(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    candidate = value.strip().upper()
    if not candidate:
        return None
    if candidate.isdigit() and len(candidate) < 6:
        candidate = candidate.zfill(6)
    return candidate


def _resolve_label(db: Session, ticker: str) -> str:
    metadata = db.get(SecurityMetadata, ticker)
    if metadata and metadata.corp_name:
        return metadata.corp_name
    return ticker


def _load_price_rows(db: Session, ticker: str, start: date, end: date) -> List[Price]:
    return (
        db.query(Price)
        .filter(Price.symbol == ticker, Price.date >= start, Price.date <= end)
        .order_by(asc(Price.date))
        .all()
    )


def _normalize_series(rows: Sequence[Price], *, max_points: int) -> Tuple[List[Dict[str, float]], List[float]]:
    series: List[Dict[str, float]] = []
    returns: List[float] = []
    base_price: Optional[float] = None
    trimmed = list(rows[-max_points:]) if max_points else list(rows)
    for row in trimmed:
        close_value = row.adj_close or row.close
        if close_value is None:
            continue
        price = float(close_value)
        if base_price is None:
            if price == 0:
                continue
            base_price = price
        if not base_price:
            continue
        normalized = (price / base_price - 1.0) * 100.0
        series.append({"date": row.date.isoformat(), "value": round(normalized, 4)})
        if row.ret is not None:
            returns.append(float(row.ret))
    return series, returns


def _lookup_ticker_by_label(db: Session, label: str) -> Optional[str]:
    normalized = label.strip()
    if not normalized:
        return None
    lowered = normalized.lower()
    candidate = (
        db.query(SecurityMetadata)
        .filter(
            (SecurityMetadata.ticker == normalized.upper())
            | (func.lower(SecurityMetadata.corp_name) == lowered)
        )
        .first()
    )
    if candidate:
        return candidate.ticker
    # try partial match
    partial = (
        db.query(SecurityMetadata)
        .filter(func.lower(SecurityMetadata.corp_name).like(f"%{lowered}%"))
        .first()
    )
    return partial.ticker if partial else None


def _enrich_entries_with_metadata(db: Session, payload: Dict[str, List[Dict[str, str]]]) -> Dict[str, List[Dict[str, str]]]:
    enriched: Dict[str, List[Dict[str, str]]] = {}
    for key, entries in payload.items():
        decorated: List[Dict[str, str]] = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            label_value = entry.get("label") or entry.get("name") or entry.get("ticker") or ""
            clean_label = label_value.strip() or "Unknown"
            ticker_value = _normalize_ticker(entry.get("ticker"))
            if not ticker_value and clean_label and db is not None:
                ticker_value = _lookup_ticker_by_label(db, clean_label)
            decorated.append(
                {
                    "ticker": ticker_value or "",
                    "label": clean_label,
                }
            )
        enriched[key] = decorated
    return enriched


def _persist_value_chain_async(center_ticker: str, payload: Dict[str, List[Dict[str, str]]]) -> None:
    if not payload or not center_ticker:
        return

    def _task() -> None:
        session = SessionLocal()
        try:
            value_chain_repository.upsert_relations(session, center_ticker, payload)
            session.commit()
        except Exception as exc:  # pragma: no cover - background logging only
            session.rollback()
            logger.debug("Value chain persistence failed for %s: %s", center_ticker, exc, exc_info=True)
        finally:
            session.close()

    threading.Thread(target=_task, name=f"value-chain-{center_ticker}", daemon=True).start()


def _jit_generate_value_chain(db: Session, ticker: str) -> Optional[Dict[str, List[Dict[str, str]]]]:
    normalized = _normalize_ticker(ticker)
    if not normalized:
        return None
    try:
        from services import rag_service  # type: ignore
    except Exception:
        rag_service = None  # type: ignore
    summaries: List[Dict[str, Any]] = []
    if rag_service:
        try:
            summaries = rag_service.search_news_summaries(normalized, ticker=normalized, limit=5)
        except Exception as exc:  # pragma: no cover - network failures
            logger.debug("Value chain JIT news retrieval failed for %s: %s", normalized, exc, exc_info=True)
    lines: List[str] = []
    for entry in summaries or []:
        summary = entry.get("summary")
        if not summary:
            continue
        title = entry.get("title") or entry.get("source") or ""
        lines.append(f"{title}: {summary}")
        if len(lines) >= 5:
            break
    context_text = "\n".join(lines).strip()
    if not context_text:
        return None
    try:
        from llm import llm_service
        extraction = llm_service.extract_value_chain_relations(normalized, context_text)
    except Exception as exc:  # pragma: no cover - LLM failure
        logger.warning("Value chain extraction failed for %s: %s", normalized, exc, exc_info=True)
        return None
    if not isinstance(extraction, dict):
        return None
    payload: Dict[str, List[Dict[str, str]]] = {
        "suppliers": extraction.get("suppliers") or [],
        "customers": extraction.get("customers") or [],
        "competitors": extraction.get("competitors") or [],
    }
    if not any(payload.values()):
        return None
    enriched_payload = _enrich_entries_with_metadata(db, payload)
    VALUE_CHAIN_CACHE[normalized] = enriched_payload
    _persist_value_chain_async(normalized, enriched_payload)
    return enriched_payload


def get_peer_group(
    db: Session,
    ticker: str,
    *,
    max_size: int = 4,
) -> List[str]:
    normalized = _normalize_ticker(ticker)
    if not normalized:
        return []
    peers: List[str] = [normalized]
    configured = PEER_FALLBACK_MAP.get(normalized, [])
    peers.extend(configured)

    if len(peers) < max_size + 1:
        metadata = db.get(SecurityMetadata, normalized)
        if metadata and metadata.cap_bucket:
            rows: Iterable[Tuple[str]] = (
                db.query(SecurityMetadata.ticker)
                .filter(
                    SecurityMetadata.cap_bucket == metadata.cap_bucket,
                    SecurityMetadata.market == metadata.market,
                    SecurityMetadata.ticker != normalized,
                )
                .order_by(SecurityMetadata.market_cap.desc())
                .limit(max_size + 2)
                .all()
            )
            for (symbol,) in rows:
                if symbol:
                    peers.append(symbol)

    unique: List[str] = []
    for symbol in peers:
        normalized_symbol = _normalize_ticker(symbol)
        if not normalized_symbol:
            continue
        if normalized_symbol in unique:
            continue
        unique.append(normalized_symbol)
        if len(unique) >= max_size + 1:
            break
    return unique


def get_normalized_returns(
    db: Session,
    tickers: Sequence[str],
    *,
    period_days: int = DEFAULT_PERIOD_DAYS,
    end_date: Optional[date] = None,
) -> Dict[str, Dict[str, object]]:
    end = end_date or date.today()
    # Fetch slightly longer window to tolerate holidays
    start = end - timedelta(days=period_days * 2)
    result: Dict[str, Dict[str, object]] = {}

    for raw_symbol in tickers:
        symbol = _normalize_ticker(raw_symbol)
        if not symbol:
            continue
        rows = _load_price_rows(db, symbol, start, end)
        if not rows:
            continue
        series, returns = _normalize_series(rows, max_points=period_days)
        if len(series) < MIN_DATA_POINTS:
            continue
        result[symbol] = {
            "ticker": symbol,
            "label": _resolve_label(db, symbol),
            "data": series,
            "latest": series[-1]["value"] if series else None,
            "returns": returns[-period_days:],
        }

    return result


def _format_value_chain_payload(
    raw_data: Optional[Dict[str, List[Dict[str, str]]]],
    *,
    base_symbol: str,
    peers: Sequence[str],
    label_lookup: Dict[str, str],
) -> Tuple[Optional[Dict[str, object]], Optional[str]]:
    if not raw_data:
        return None, None

    def _prepare(entries: Optional[List[Dict[str, str]]]) -> List[Dict[str, str]]:
        prepared: List[Dict[str, str]] = []
        for entry in entries or []:
            if not isinstance(entry, dict):
                continue
            symbol = entry.get("ticker") or ""
            normalized_symbol = _normalize_ticker(symbol) if symbol else None
            label_value = entry.get("label") or entry.get("name") or normalized_symbol or symbol or ""
            prepared.append(
                {
                    "ticker": normalized_symbol or symbol or "",
                    "label": label_lookup.get(normalized_symbol or symbol or "", label_value or ""),
                }
            )
            if len(prepared) >= 5:
                break
        return prepared

    target_payload = {
        "ticker": base_symbol,
        "label": label_lookup.get(base_symbol, base_symbol),
    }

    suppliers = _prepare(raw_data.get("suppliers"))
    customers = _prepare(raw_data.get("customers"))
    peer_nodes = _prepare(raw_data.get("competitors") or raw_data.get("peers"))
    if not peer_nodes:
        for peer_symbol in peers[1:]:
            if peer_symbol == base_symbol:
                continue
            peer_nodes.append(
                {
                    "ticker": peer_symbol,
                    "label": label_lookup.get(peer_symbol, peer_symbol),
                }
            )
            if len(peer_nodes) >= 4:
                break

    summary_parts: List[str] = []
    if suppliers:
        summary_parts.append("주요 공급사: " + ", ".join(entry["label"] for entry in suppliers[:4]))
    if customers:
        summary_parts.append("주요 고객사: " + ", ".join(entry["label"] for entry in customers[:4]))
    if peer_nodes:
        summary_parts.append("경쟁/동종사: " + ", ".join(entry["label"] for entry in peer_nodes[:4]))
    summary_text = " / ".join(summary_parts) if summary_parts else None

    payload = {
        "target": target_payload,
        "suppliers": suppliers,
        "customers": customers,
        "peers": peer_nodes,
    }
    if summary_text:
        payload["summary"] = summary_text
    return payload, summary_text


def _compute_peer_average(series_map: Dict[str, Dict[str, object]], base: str) -> Optional[Dict[str, object]]:
    peer_dates: Dict[str, List[float]] = defaultdict(list)
    for symbol, payload in series_map.items():
        if symbol == base:
            continue
        for point in payload.get("data", []):
            peer_dates[point["date"]].append(float(point["value"]))
    if not peer_dates:
        return None
    aggregated = [
        {"date": date_key, "value": round(mean(values), 4)}
        for date_key, values in peer_dates.items()
        if values
    ]
    aggregated.sort(key=lambda entry: entry["date"])
    latest = aggregated[-1]["value"] if aggregated else None
    return {"label": "Peer Avg", "ticker": "PEER_AVG", "data": aggregated, "latest": latest}


def _pearson_correlation(xs: Sequence[float], ys: Sequence[float]) -> Optional[float]:
    if not xs or not ys:
        return None
    paired = [(x, y) for x, y in zip(xs, ys) if isinstance(x, (int, float)) and isinstance(y, (int, float))]
    if len(paired) < MIN_DATA_POINTS:
        return None
    x_values, y_values = zip(*paired)
    mean_x = sum(x_values) / len(x_values)
    mean_y = sum(y_values) / len(y_values)
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in paired)
    denominator = (sum((x - mean_x) ** 2 for x in x_values) * sum((y - mean_y) ** 2 for y in y_values)) ** 0.5
    if not denominator:
        return None
    return round(numerator / denominator, 4)


def build_peer_comparison(
    db: Session,
    ticker: str,
    *,
    period_days: int = DEFAULT_PERIOD_DAYS,
) -> Dict[str, object]:
    peers = get_peer_group(db, ticker)
    if not peers:
        raise ValueError("peer_group_unavailable")
    series_map = get_normalized_returns(db, peers, period_days=period_days)
    base_symbol = peers[0]
    base_payload = series_map.get(base_symbol)
    if not base_payload:
        raise ValueError("price_data_missing")

    label_lookup = {symbol: payload.get("label") or symbol for symbol, payload in series_map.items()}

    peer_avg = _compute_peer_average(series_map, base_symbol)
    latest_cards = [
        {
            "ticker": base_symbol,
            "label": base_payload.get("label"),
            "value": base_payload.get("latest"),
        }
    ]
    interpretation = "동일 기간 비교가 충분하지 않습니다."
    if peer_avg:
        latest_cards.append(
            {"ticker": peer_avg["ticker"], "label": peer_avg["label"], "value": peer_avg.get("latest")}
        )
        base_value = base_payload.get("latest")
        peer_value = peer_avg.get("latest")
        if isinstance(base_value, (int, float)) and isinstance(peer_value, (int, float)):
            delta = base_value - peer_value
            if abs(delta) < 1:
                interpretation = "섹터 평균과 거의 동일한 흐름입니다."
            elif delta < 0:
                interpretation = "기준 종목이 섹터 대비 약세입니다. 기업 고유 이슈 여부를 확인하세요."
            else:
                interpretation = "기준 종목이 섹터 대비 강세입니다. 경쟁사 대비 긍정 요인이 있습니다."

    correlations: List[Dict[str, object]] = []
    base_returns = base_payload.get("returns", [])
    for symbol, payload in series_map.items():
        if symbol == base_symbol:
            continue
        corr = _pearson_correlation(
            base_returns,
            payload.get("returns", []),
        )
        correlations.append(
            {
                "ticker": symbol,
                "label": payload.get("label"),
                "value": corr,
            }
        )

    series_response = [
        {
            "ticker": symbol,
            "label": payload.get("label"),
            "data": payload.get("data", []),
        }
        for symbol, payload in series_map.items()
    ]
    if peer_avg:
        series_response.append(
            {
                "ticker": peer_avg["ticker"],
                "label": peer_avg["label"],
                "data": peer_avg["data"],
                "isAverage": True,
            }
        )

    raw_value_chain = VALUE_CHAIN_CACHE.get(base_symbol)
    if raw_value_chain is None:
        # 1. Try loading from DB
        try:
            persisted = value_chain_repository.load_relations(db, base_symbol)
            if any(persisted.values()):
                raw_value_chain = persisted
                VALUE_CHAIN_CACHE[base_symbol] = persisted
        except Exception as exc:
            logger.warning("Failed to load value chain from DB for %s: %s", base_symbol, exc)

    if raw_value_chain is None:
        # 2. Fallback to JIT generation
        raw_value_chain = _jit_generate_value_chain(db, base_symbol)
    
    value_chain, value_chain_summary = _format_value_chain_payload(
        raw_value_chain,
        base_symbol=base_symbol,
        peers=peers,
        label_lookup=label_lookup,
    )

    return {
        "ticker": base_symbol,
        "label": base_payload.get("label"),
        "periodDays": period_days,
        "peers": [
            {"ticker": symbol, "label": series_map.get(symbol, {}).get("label", symbol)}
            for symbol in peers[1:]
            if symbol in series_map
        ],
        "series": series_response,
        "latest": latest_cards,
        "interpretation": interpretation,
        "correlations": correlations,
        "valueChain": value_chain,
        "valueChainSummary": value_chain_summary,
    }


__all__ = [
    "get_peer_group",
    "get_normalized_returns",
    "build_peer_comparison",
]
