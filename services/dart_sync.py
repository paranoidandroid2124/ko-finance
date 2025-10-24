"""Synchronise extended DART disclosures (DE002~DE005) into normalized tables."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Dict, Optional, Sequence, Tuple

from sqlalchemy.orm import Session

from core.logging import get_logger
from ingest.dart_client import DartClient
from models.company import CorpMetric, FilingEvent, InsiderTransaction
from models.filing import Filing

logger = get_logger(__name__)

_REPRT_CODE_MAP = {
    "사업보고서": "11014",
    "연결감사보고서": "11014",
    "반기보고서": "11012",
    "분기보고서": "11013",
    "1분기보고서": "11011",
}

_PERIOD_LABELS = {
    "11011": "Q1",
    "11012": "Q2",
    "11013": "Q3",
    "11014": "FY",
}

_MNA_KEYWORDS = ("합병", "인수", "양수", "양도", "영업양수도", "merger", "acquisition", "consolidation")
_CB_KEYWORDS = ("전환사채", "convertible bond", "cb ", "cb-")


def sync_additional_disclosures(db: Session, client: DartClient, filing: Filing) -> None:
    """Fetch DE002~DE005 datasets for a newly seeded filing."""
    if not filing.corp_code:
        logger.debug("Skipping extended DART sync for filing %s (missing corp_code).", filing.id)
        return

    bsns_year, reprt_code = _infer_reporting_context(filing)
    if reprt_code:
        _sync_financial_summaries(db, client, filing, bsns_year, reprt_code)
        _sync_financial_accounts(db, client, filing, bsns_year, reprt_code)
        _sync_major_shareholders(db, client, filing, bsns_year, reprt_code)
    else:
        logger.debug(
            "Filing %s (%s) does not map to a periodic report, skipping DE002/DE003/DE004.",
            filing.id,
            filing.report_name,
        )

    _sync_major_issues(db, client, filing, bsns_year, reprt_code)


def _infer_reporting_context(filing: Filing) -> Tuple[int, Optional[str]]:
    """Return (business year, reprt_code) inferred from filing metadata."""
    filed_at = filing.filed_at or datetime.utcnow()
    bsns_year = filed_at.year
    report_name = (filing.report_name or filing.title or "").strip()

    reprt_code: Optional[str] = None
    normalized = report_name.replace(" ", "")
    for key, code in _REPRT_CODE_MAP.items():
        if key in report_name or key in normalized:
            reprt_code = code
            break

    # If quarterly descriptor present specify quarter explicitly.
    if "1분기" in report_name or "제1" in report_name:
        reprt_code = "11011"
    elif "3분기" in report_name or "제3" in report_name:
        reprt_code = "11013"

    return bsns_year, reprt_code


# ---------------------------------------------------------------------------
# Financial metrics (DE002)
# ---------------------------------------------------------------------------

def _sync_financial_summaries(
    db: Session,
    client: DartClient,
    filing: Filing,
    bsns_year: int,
    reprt_code: str,
) -> None:
    response = client.fetch_single_account_summary(filing.corp_code, bsns_year, reprt_code)
    rows: Sequence[Dict[str, Any]] = response.get("list") or []
    if not rows:
        logger.debug(
            "No DE002 summary rows for filing %s (corp_code=%s, year=%s, reprt_code=%s).",
            filing.id,
            filing.corp_code,
            bsns_year,
            reprt_code,
        )
        return

    for row in rows:
        _persist_account_row(
            db=db,
            filing=filing,
            row=row,
            reprt_code=reprt_code,
            source="DE002",
        )

    db.commit()
    logger.info(
        "Upserted %d DE002 financial summary rows for filing %s.",
        len(rows),
        filing.receipt_no or filing.id,
    )


# ---------------------------------------------------------------------------
# Financial accounts (DE003)
# ---------------------------------------------------------------------------

def _sync_financial_accounts(
    db: Session,
    client: DartClient,
    filing: Filing,
    bsns_year: int,
    reprt_code: str,
) -> None:
    response = client.fetch_single_account_detail(filing.corp_code, bsns_year, reprt_code)
    rows: Sequence[Dict[str, Any]] = response.get("list") or []
    if not rows:
        logger.debug(
            "No DE003 account rows for filing %s (corp_code=%s, year=%s, reprt_code=%s).",
            filing.id,
            filing.corp_code,
            bsns_year,
            reprt_code,
        )
        return

    for row in rows:
        _persist_account_row(
            db=db,
            filing=filing,
            row=row,
            reprt_code=reprt_code,
            source="DE003",
        )

    db.commit()
    logger.info(
        "Upserted %d DE003 financial account rows for filing %s.",
        len(rows),
        filing.receipt_no or filing.id,
    )


def _persist_account_row(
    db: Session,
    filing: Filing,
    row: Dict[str, Any],
    reprt_code: str,
    source: str,
) -> None:
    account_name = (row.get("account_nm") or row.get("accountName") or "").strip()
    if not account_name:
        return
    account_code = (row.get("account_id") or row.get("accountCd") or account_name).strip()
    group_name = (row.get("sj_nm") or row.get("sj_div") or row.get("statement") or "").strip() or None
    unit = (row.get("unit_nm") or row.get("unit") or "").strip() or None

    for prefix in ("thstrm", "frmtrm", "bfefrmtrm"):
        amount_key = f"{prefix}_amount"
        if amount_key not in row:
            continue
        value = _parse_float(row.get(amount_key))
        if value is None:
            continue

        period_label = _normalize_period_label(row.get(f"{prefix}_nm"), reprt_code, prefix)
        period_end = _parse_date(row.get(f"{prefix}_dt"))

        metric = _get_or_create_metric(
            db=db,
            corp_code=filing.corp_code,
            metric_code=account_code,
            fiscal_year=_resolve_fiscal_year(row, prefix, filing),
            fiscal_period=period_label,
            source=source,
        )

        metric.corp_name = filing.corp_name
        metric.ticker = filing.ticker
        metric.metric_name = account_name
        metric.metric_group = group_name
        metric.period_end_date = period_end
        metric.value = value
        metric.unit = unit
        metric.reference_no = filing.receipt_no
        metric.raw_payload = row

        db.add(metric)


def _get_or_create_metric(
    db: Session,
    corp_code: str,
    metric_code: str,
    fiscal_year: int,
    fiscal_period: str,
    source: str,
) -> CorpMetric:
    existing = (
        db.query(CorpMetric)
        .filter(
            CorpMetric.corp_code == corp_code,
            CorpMetric.metric_code == metric_code,
            CorpMetric.fiscal_year == fiscal_year,
            CorpMetric.fiscal_period == fiscal_period,
            CorpMetric.source == source,
        )
        .one_or_none()
    )
    if existing:
        return existing
    return CorpMetric(
        corp_code=corp_code,
        metric_code=metric_code,
        fiscal_year=fiscal_year,
        fiscal_period=fiscal_period,
        source=source,
    )


def _resolve_fiscal_year(row: Dict[str, Any], prefix: str, filing: Filing) -> int:
    year = _extract_year(row.get(f"{prefix}_dt")) or _extract_year(row.get(f"{prefix}_nm"))
    if year:
        return year
    filed_at = filing.filed_at or datetime.utcnow()
    return filed_at.year


def _extract_year(value: Optional[str]) -> Optional[int]:
    if not value:
        return None
    match = re.search(r"(20\d{2})", value)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            return None
    return None


def _normalize_period_label(raw_label: Optional[str], reprt_code: Optional[str], prefix: str) -> str:
    if raw_label:
        cleaned = raw_label.strip()
        # Map Korean descriptors to canonical values.
        for keyword, label in {
            "당기": "Current",
            "전기": "Prior",
            "전전기": "PriorPrior",
            "3분기": "Q3",
            "반기": "Q2",
            "1분기": "Q1",
            "말": "FY",
        }.items():
            if keyword in cleaned:
                return label
        return cleaned
    if reprt_code and reprt_code in _PERIOD_LABELS:
        return _PERIOD_LABELS[reprt_code]
    return prefix.upper()


# ---------------------------------------------------------------------------
# Insider / major shareholder (DE004)
# ---------------------------------------------------------------------------

def _sync_major_shareholders(
    db: Session,
    client: DartClient,
    filing: Filing,
    bsns_year: int,
    reprt_code: str,
) -> None:
    response = client.fetch_major_shareholders(filing.corp_code, bsns_year, reprt_code)
    rows: Sequence[Dict[str, Any]] = response.get("list") or []
    if not rows:
        logger.debug(
            "No DE004 (majorstock) rows for filing %s.",
            filing.receipt_no or filing.id,
        )
        return

    for row in rows:
        transaction = _get_or_create_transaction(
            db=db,
            corp_code=filing.corp_code,
            receipt_no=filing.receipt_no or "",
            person_name=(row.get("psn_nm") or row.get("nm") or "UNKNOWN").strip(),
            transaction_date=_parse_date(row.get("chg_de") or row.get("bsis_de") or row.get("de")),
        )
        transaction.corp_name = filing.corp_name
        transaction.ticker = filing.ticker
        transaction.report_name = filing.report_name
        transaction.relation = (row.get("rl_nm") or row.get("ofcps") or "").strip() or None
        change = _parse_float(row.get("chg_stkqy") or row.get("change_shr"))
        after = _parse_float(row.get("stkqy") or row.get("after_stkqy"))
        before = _parse_float(row.get("stkqy") or row.get("before_stkqy"))
        if before is None and after is not None and change is not None:
            before = after - change
        elif after is None and before is not None and change is not None:
            after = before + change
        transaction.shares_before = before
        transaction.shares_after = after
        transaction.shares_change = change

        ratio_change = _parse_float(row.get("chg_stkrt") or row.get("change_rt"))
        ratio_after = _parse_float(row.get("stkrt") or row.get("after_stkrt"))
        ratio_before = _parse_float(row.get("stkrt_bf") or row.get("before_stkrt"))
        if ratio_before is None and ratio_after is not None and ratio_change is not None:
            ratio_before = ratio_after - ratio_change
        elif ratio_after is None and ratio_before is not None and ratio_change is not None:
            ratio_after = ratio_before + ratio_change
        transaction.ratio_before = ratio_before
        transaction.ratio_after = ratio_after
        transaction.ratio_change = ratio_change

        transaction.transaction_type = _classify_transaction(change)
        transaction.acquisition_amount = _parse_float(row.get("acqs_mony") or row.get("change_amount"))
        transaction.payload = row
        transaction.source = "DE004"

        db.add(transaction)

    db.commit()
    logger.info(
        "Upserted %d insider transactions for filing %s.",
        len(rows),
        filing.receipt_no or filing.id,
    )


def _get_or_create_transaction(
    db: Session,
    corp_code: str,
    receipt_no: str,
    person_name: str,
    transaction_date: Optional[date],
) -> InsiderTransaction:
    existing = (
        db.query(InsiderTransaction)
        .filter(
            InsiderTransaction.corp_code == corp_code,
            InsiderTransaction.receipt_no == receipt_no,
            InsiderTransaction.person_name == person_name,
            InsiderTransaction.transaction_date == transaction_date,
        )
        .one_or_none()
    )
    if existing:
        return existing
    return InsiderTransaction(
        corp_code=corp_code,
        receipt_no=receipt_no,
        person_name=person_name,
        transaction_date=transaction_date,
    )


def _classify_transaction(change: Optional[float]) -> Optional[str]:
    if change is None:
        return None
    if change > 0:
        return "buy"
    if change < 0:
        return "sell"
    return "hold"


# ---------------------------------------------------------------------------
# Major issues (DE005)
# ---------------------------------------------------------------------------

def _sync_major_issues(
    db: Session,
    client: DartClient,
    filing: Filing,
    bsns_year: int,
    reprt_code: Optional[str],
) -> None:
    response = client.fetch_major_issues(filing.corp_code, bsns_year, reprt_code)
    rows: Sequence[Dict[str, Any]] = response.get("list") or []
    if not rows:
        logger.debug("No DE005 (majorissue) rows for filing %s.", filing.receipt_no or filing.id)
        return

    for row in rows:
        event_type = (row.get("ty_nm") or row.get("type_nm") or row.get("sj_nm") or "").strip() or "Unknown"
        event_name = (row.get("report_nm") or row.get("event_content") or row.get("title") or "").strip() or None
        event_date = _parse_date(row.get("occurrence_de") or row.get("occr_de") or row.get("event_de"))
        resolution_date = _parse_date(row.get("decision_de") or row.get("resltn_de"))
        event = (
            db.query(FilingEvent)
            .filter(
                FilingEvent.corp_code == filing.corp_code,
                FilingEvent.receipt_no == (filing.receipt_no or ""),
                FilingEvent.event_type == event_type,
                FilingEvent.event_name == event_name,
            )
            .one_or_none()
        )
        if not event:
            event = FilingEvent(
                corp_code=filing.corp_code,
                receipt_no=filing.receipt_no or "",
                event_type=event_type,
                event_name=event_name,
            )

        event.corp_name = filing.corp_name
        event.ticker = filing.ticker
        event.report_name = filing.report_name
        event.event_date = event_date
        event.resolution_date = resolution_date
        event.payload = row
        event.source = "DE005"
        event.derived_metrics = _derive_event_metrics(event_type, event_name, row)

        db.add(event)

    db.commit()
    logger.info(
        "Upserted %d major issue events for filing %s.",
        len(rows),
        filing.receipt_no or filing.id,
    )


def _derive_event_metrics(event_type: str, event_name: Optional[str], payload: Dict[str, Any]) -> Dict[str, Any]:
    derived: Dict[str, Any] = {}
    text = f"{event_type} {event_name or ''}".lower()

    derived["mna_flag"] = any(keyword.lower() in text for keyword in _MNA_KEYWORDS)
    derived["cb_related"] = any(keyword.lower() in text for keyword in _CB_KEYWORDS)

    if derived["cb_related"]:
        dilution = _extract_dilution_ratio(payload)
        if dilution is not None:
            derived["cb_dilution_ratio"] = dilution

    return derived


def _extract_dilution_ratio(payload: Dict[str, Any]) -> Optional[float]:
    for key, value in payload.items():
        if not isinstance(value, str):
            continue
        lowered = key.lower()
        if "dilut" in lowered or "dilution" in lowered or lowered.endswith("_rt"):
            ratio = _parse_float(value)
            if ratio is not None:
                return ratio / 100 if ratio > 1 else ratio
    return None


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def _parse_float(raw: Any) -> Optional[float]:
    if raw in (None, "", "-", "--"):
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    text = str(raw).strip()
    if not text:
        return None
    text = text.replace(",", "").replace("%", "")
    try:
        return float(text)
    except ValueError:
        return None


def _parse_date(raw: Any) -> Optional[date]:
    if not raw:
        return None
    if isinstance(raw, date):
        return raw
    text = str(raw).strip()
    if not text:
        return None
    for fmt in ("%Y%m%d", "%Y.%m.%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    # Handle values like "2023년 12월 31일"
    match = re.search(r"(20\d{2})[^\d]*(\d{1,2})[^\d]*(\d{1,2})", text)
    if match:
        try:
            year, month, day = map(int, match.groups())
            return date(year, month, day)
        except ValueError:
            return None
    return None
