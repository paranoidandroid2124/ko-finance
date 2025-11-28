"""Disclosure viewer tool router (alias to /tools/disclosure-viewer)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from web.routers.tools import run_disclosure_viewer

router = APIRouter(prefix="/disclosure-viewer", tags=["Disclosure"])


@router.get("")
def disclosure_viewer_alias(
    filing_id: str | None = None,
    receipt_no: str | None = None,
    highlight_query: str | None = None,
    top_k: int = 3,
    db: Session = Depends(get_db),
):
    """Alias endpoint that forwards to /tools/disclosure-viewer."""
    return run_disclosure_viewer(
        filing_id=filing_id,
        receipt_no=receipt_no,
        highlight_query=highlight_query,
        top_k=top_k,
        db=db,
    )


__all__ = ["router"]
