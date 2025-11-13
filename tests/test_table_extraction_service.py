import uuid

import pytest

from models.filing import Filing
from models.table_extraction import TableCell, TableMeta
from parse.table_extraction import TableCellPayload, TableExtractionResult
from services import table_extraction_service


class _DummyExtractor:
    def __init__(self, *, results):
        self._results = results

    def extract(self, pdf_path: str):
        self.last_pdf = pdf_path
        return self._results


def _fixture_result() -> TableExtractionResult:
    payload = TableCellPayload(
        row_index=0,
        column_index=0,
        header_path=["배당", "구분"],
        raw_value="1,000",
        normalized_value="1,000",
        numeric_value=1000.0,
        value_type="number",
        confidence=0.92,
    )
    payload2 = TableCellPayload(
        row_index=0,
        column_index=1,
        header_path=["배당", "세부"],
        raw_value="우선주",
        normalized_value="우선주",
        numeric_value=None,
        value_type="text",
        confidence=0.75,
    )
    stats = {
        "headerRows": 1,
        "rowCount": 1,
        "columnCount": 2,
        "nonEmptyCells": 2,
        "nonEmptyRatio": 1.0,
        "headerCoverage": 1.0,
        "numericRatio": 0.5,
    }
    return TableExtractionResult(
        page_number=1,
        table_index=1,
        bbox=(0.0, 0.0, 10.0, 10.0),
        header_rows=[["배당", "세부"]],
        body_rows=[["1,000", "우선주"]],
        header_paths=[["배당", "구분"], ["배당", "세부"]],
        table_type="dividend",
        matched_keywords=["배당"],
        title="배당 요약",
        confidence=0.91,
        stats=stats,
        html="<table><tbody><tr><td>1,000</td><td>우선주</td></tr></tbody></table>",
        csv="배당,세부\n1,000,우선주\n",
        json_payload={"headerRows": [["배당", "세부"]], "bodyRows": [["1,000", "우선주"]], "headerPaths": [["배당", "구분"], ["배당", "세부"]], "bbox": [0.0, 0.0, 10.0, 10.0], "metrics": stats},
        cells=[payload, payload2],
        checksum="deadbeef",
        duration_ms=12.5,
    )


def test_extract_tables_for_filing_persists_metadata(db_session, tmp_path, monkeypatch):
    pdf_path = tmp_path / "sample.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n%EOF")

    filing = Filing(
        id=uuid.uuid4(),
        receipt_no="20251110000235",
        corp_code="00126380",
        corp_name="테스트",
        ticker="005930",
        file_path=str(pdf_path),
    )
    db_session.add(filing)
    db_session.commit()

    fake_result = _fixture_result()

    extractor = _DummyExtractor(results=[fake_result])
    monkeypatch.setattr(table_extraction_service, "TableExtractor", lambda **kwargs: extractor)
    monkeypatch.setattr(table_extraction_service, "_WRITE_ARTIFACTS", False)

    stats = table_extraction_service.extract_tables_for_filing(
        db_session,
        filing=filing,
        pdf_path=str(pdf_path),
        max_pages=5,
        max_tables=5,
        time_budget_seconds=30,
    )

    assert stats["stored"] == 1
    assert stats["deleted"] == 0
    assert extractor.last_pdf == str(pdf_path)

    stored_meta = db_session.query(TableMeta).filter_by(filing_id=filing.id).one()
    assert stored_meta.table_type == "dividend"
    assert stored_meta.table_title == "배당 요약"
    assert stored_meta.non_empty_cells == 2
    assert stored_meta.extra["sourcePdf"] == str(pdf_path)
    assert stored_meta.column_headers == [["배당", "구분"], ["배당", "세부"]]

    cells = db_session.query(TableCell).filter_by(table_id=stored_meta.id).order_by(TableCell.column_index).all()
    assert len(cells) == 2
    assert cells[0].numeric_value == 1000.0
    assert cells[1].value_type == "text"
