"""Helpers for persisting value-chain relations."""

from __future__ import annotations

from typing import Dict, Iterable, Mapping

from sqlalchemy.orm import Session

from models.value_chain import ValueChainEdge


RelationPayload = Mapping[str, Iterable[Mapping[str, str]]]


def _coerce_label(value: str | None) -> str:
    if not value:
        return "Unknown"
    return value.strip() or "Unknown"


def _coerce_ticker(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = value.strip().upper()
    return cleaned or None


def upsert_relations(
    db: Session,
    center_ticker: str,
    payload: RelationPayload,
) -> None:
    """Persist extracted relations into the value_chain_edges table."""

    if not center_ticker or not payload:
        return

    center = center_ticker.strip().upper()
    for key, entries in payload.items():
        if not entries:
            continue
        relation_type = key.rstrip("s")
        for entry in entries:
            if not isinstance(entry, Mapping):
                continue
            label = _coerce_label(entry.get("label") or entry.get("name") or entry.get("ticker"))
            ticker_value = _coerce_ticker(entry.get("ticker"))
            evidence = entry.get("evidence") if isinstance(entry.get("evidence"), str) else None
            weight_value = None
            raw_weight = entry.get("weight")
            if isinstance(raw_weight, (int, float)):
                weight_value = float(raw_weight)
            existing = (
                db.query(ValueChainEdge)
                .filter(
                    ValueChainEdge.center_ticker == center,
                    ValueChainEdge.relation_type == relation_type,
                    ValueChainEdge.related_label == label,
                )
                .first()
            )
            if existing:
                existing.related_ticker = ticker_value or existing.related_ticker
                existing.weight = weight_value if weight_value is not None else existing.weight
                existing.evidence = evidence or existing.evidence
            else:
                db.add(
                    ValueChainEdge(
                        center_ticker=center,
                        relation_type=relation_type,
                        related_ticker=ticker_value,
                        related_label=label,
                        weight=weight_value,
                        evidence=evidence,
                    )
                )


def load_relations(db: Session, center_ticker: str) -> Dict[str, list[Dict[str, str]]]:
    """Load persisted relations for a ticker from the database."""
    if not center_ticker:
        return {}

    center = center_ticker.strip().upper()
    rows = (
        db.query(ValueChainEdge)
        .filter(ValueChainEdge.center_ticker == center)
        .all()
    )

    result: Dict[str, list[Dict[str, str]]] = {
        "suppliers": [],
        "customers": [],
        "competitors": [],
    }

    for row in rows:
        key = f"{row.relation_type}s"  # supplier -> suppliers
        if key not in result:
            # Fallback for unknown types or if 'peers' stored as 'competitor'
            if row.relation_type == "peer":
                key = "competitors"
            else:
                continue
        
        entry = {
            "label": row.related_label,
            "ticker": row.related_ticker,
            "evidence": row.evidence,
        }
        # Filter out None values
        cleaned = {k: v for k, v in entry.items() if v is not None}
        result[key].append(cleaned)

    return result


__all__ = ["upsert_relations", "load_relations"]
