"""Board viewer API exposing watchlist/sector summaries."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from database import get_db
from schemas.api.boards import (
    BoardDetailResponse,
    BoardEntrySchema,
    BoardEventSchema,
    BoardListResponse,
    BoardSummarySchema,
)
from services.watchlist_aggregator import (
    build_board_entries as aggregate_board_entries,
    build_board_timeline as aggregate_board_timeline,
    collect_watchlist_items,
    summarise_watchlist_rules,
    WatchlistRuleSummary,
)
from web.deps_rbac import RbacState, get_rbac_state

router = APIRouter(prefix="/boards", tags=["Boards"])

BOARD_FETCH_LIMIT = 400


def _infer_board_type(item: Mapping[str, Any]) -> str:
    tags = item.get("ruleTags") or []
    normalized = [str(tag or "").lower() for tag in tags if tag]
    if any("sector" in tag for tag in normalized):
        return "sector"
    if any("theme" in tag or "basket" in tag for tag in normalized):
        return "theme"
    return "watchlist"


def _normalize_rule_id(value: Any) -> str:
    return str(value or "").strip()


def _normalize_ticker(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    normalized = value.strip().upper()
    return normalized or None


def _item_contains_ticker(item: Mapping[str, Any], ticker: str) -> bool:
    candidate = _normalize_ticker(item.get("ticker"))
    if candidate and candidate == ticker:
        return True
    rule_tickers = item.get("ruleTickers") or []
    if isinstance(rule_tickers, Iterable):
        for value in rule_tickers:
            if _normalize_ticker(value) == ticker:
                return True
    return False


def _filter_items_by_ticker(items: Sequence[Mapping[str, Any]], ticker: str) -> List[Mapping[str, Any]]:
    return [item for item in items if _item_contains_ticker(item, ticker)]


def _build_rule_type_map(items: Sequence[Mapping[str, Any]]) -> Dict[str, str]:
    rule_types: Dict[str, str] = {}
    for item in items:
        rule_id = _normalize_rule_id(item.get("ruleId"))
        if not rule_id or rule_id in rule_types:
            continue
        rule_types[rule_id] = _infer_board_type(item)
    return rule_types


def _build_board_summary(payload: WatchlistRuleSummary, board_type: str) -> BoardSummarySchema:
    resolved_type = board_type if board_type in {"watchlist", "sector", "theme"} else "watchlist"
    return BoardSummarySchema(
        id=payload.rule_id,
        name=payload.name,
        type=resolved_type,
        description=payload.description,
        tickers=sorted(payload.tickers),
        eventCount=payload.event_count,
        recentAlerts=payload.event_count,
        channels=sorted(payload.channels),
        updatedAt=payload.last_triggered_at.isoformat() if payload.last_triggered_at else None,
    )


def _convert_entry_payloads(payloads: Sequence[Mapping[str, Any]]) -> List[BoardEntrySchema]:
    entries: List[BoardEntrySchema] = []
    for item in payloads:
        entries.append(
            BoardEntrySchema(
                ticker=str(item.get("ticker") or ""),
                corpName=item.get("corpName"),
                sector=item.get("sector"),
                eventCount=int(item.get("eventCount") or 0),
                lastHeadline=item.get("lastHeadline"),
                lastEventAt=item.get("lastEventAt"),
                sentiment=item.get("sentiment"),
                alertStatus=item.get("alertStatus") or "active",
                targetUrl=item.get("targetUrl"),
            )
        )
    return entries


def _convert_timeline_payloads(payloads: Sequence[Mapping[str, Any]]) -> List[BoardEventSchema]:
    return [
        BoardEventSchema(
            id=str(item.get("id")),
            headline=str(item.get("headline") or "Watchlist ì•Œë¦¼"),
            summary=item.get("summary"),
            channel=item.get("channel"),
            sentiment=item.get("sentiment"),
            deliveredAt=item.get("deliveredAt"),
            url=item.get("url"),
        )
        for item in payloads
    ]


@router.get("", response_model=BoardListResponse)
def list_boards(
    ticker: Optional[str] = Query(
        default=None,
        description="ëž˜í†µí•˜ëŠ” í‹°ì»¤ë¥¼ í¬í•¨í•œ ë³´ë“œë§Œ í˜„ì‹¤í™•ì¸",
    ),
    db: Session = Depends(get_db),
    state: RbacState = Depends(get_rbac_state),
) -> BoardListResponse:
    items, _ = collect_watchlist_items(
        db,
        user_id=state.user_id,
        org_id=state.org_id,
        limit=BOARD_FETCH_LIMIT,
    )
    if not items:
        return BoardListResponse(boards=[])

    normalized_ticker = _normalize_ticker(ticker)
    scoped_items = _filter_items_by_ticker(items, normalized_ticker) if normalized_ticker else list(items)
    if normalized_ticker and not scoped_items:
        return BoardListResponse(boards=[])

    rule_types = _build_rule_type_map(items)
    summaries = summarise_watchlist_rules(scoped_items)
    boards = [
        _build_board_summary(summary, rule_types.get(summary.rule_id, "watchlist"))
        for summary in summaries
    ]
    return BoardListResponse(boards=boards)


@router.get("/{board_id}", response_model=BoardDetailResponse)
def read_board(
    board_id: str,
    db: Session = Depends(get_db),
    state: RbacState = Depends(get_rbac_state),
) -> BoardDetailResponse:
    items, _ = collect_watchlist_items(
        db,
        user_id=state.user_id,
        org_id=state.org_id,
        limit=BOARD_FETCH_LIMIT,
    )
    if not items:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "boards.not_found", "message": "ìš”ì²­í•œ ë³´ë“œë¥¼ ì°¾ì„ ìˆ˜ ì—†ìŠµë‹ˆë‹¤."},
        )

    normalized_id = board_id.strip()
    filtered = [item for item in items if _normalize_rule_id(item.get("ruleId")) == normalized_id]
    if not filtered:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "boards.not_found", "message": "ìš”ì²­í•œ ë³´ë“œë¥¼ ì°¾ì„ ìˆ˜ ì—†ìŠµë‹ˆë‹¤."},
        )

    summaries = summarise_watchlist_rules(filtered)
    if not summaries:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "boards.not_found", "message": "ìš”ì²­í•œ ë³´ë“œë¥¼ ì°¾ì„ ìˆ˜ ì—†ìŠµë‹ˆë‹¤."},
        )

    rule_types = _build_rule_type_map(items)
    board_summary = _build_board_summary(summaries[0], rule_types.get(normalized_id, "watchlist"))

    entries_payload = aggregate_board_entries(filtered)
    timeline_payload = aggregate_board_timeline(filtered)
    entries = _convert_entry_payloads(entries_payload)
    timeline = _convert_timeline_payloads(timeline_payload)

    return BoardDetailResponse(board=board_summary, entries=entries, timeline=timeline)
