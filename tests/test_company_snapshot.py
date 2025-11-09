import uuid
from datetime import date, datetime
from typing import Iterator, Tuple

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from database import get_db
from models.company import CorpMetric
from models.filing import Filing
from web.routers.company import router as company_router


@pytest.fixture()
def company_api_client(db_session: Session) -> Iterator[Tuple[TestClient, Session]]:
  app = FastAPI()
  app.include_router(company_router, prefix="/api/v1")

  def override_get_db():
    yield db_session

  app.dependency_overrides[get_db] = override_get_db
  client = TestClient(app)
  try:
    yield client, db_session
  finally:
    client.close()
    app.dependency_overrides.pop(get_db, None)


def seed_financials(session) -> None:
  filing = Filing(
    id=uuid.uuid4(),
    corp_code="00123456",
    corp_name="테스트 홀딩스",
    ticker="TEST",
    title="2024 사업보고서",
    report_name="Annual Report",
    receipt_no="20240000000123",
    filed_at=datetime(2025, 1, 31),
  )
  session.add(filing)

  annual_metric = CorpMetric(
    corp_code="00123456",
    corp_name="테스트 홀딩스",
    ticker="TEST",
    metric_code="revenue",
    metric_name="매출액",
    metric_group="income_statement",
    fiscal_year=2024,
    fiscal_period="FY",
    period_end_date=date(2024, 12, 31),
    value=123_456.0,
    unit="백만 원",
    source="DE002",
    reference_no="20240000000123",
  )
  quarterly_metric = CorpMetric(
    corp_code="00123456",
    corp_name="테스트 홀딩스",
    ticker="TEST",
    metric_code="operating_income",
    metric_name="영업이익",
    metric_group="income_statement",
    fiscal_year=2024,
    fiscal_period="Q1",
    period_end_date=date(2024, 3, 31),
    value=42_000.0,
    unit="백만 원",
    source="DE003",
    reference_no="20240000000456",
  )
  session.add_all([annual_metric, quarterly_metric])
  session.commit()


def test_company_snapshot_includes_financial_statements(company_api_client):
  client, session = company_api_client
  seed_financials(session)

  response = client.get("/api/v1/companies/TEST/snapshot")
  assert response.status_code == 200, response.text

  payload = response.json()
  statements = payload["financial_statements"]
  assert isinstance(statements, list) and statements, "financial statements should not be empty"

  statement = statements[0]
  assert statement["rows"], "statement rows should be populated"

  first_row = statement["rows"][0]
  assert first_row["values"], "statement row values should be populated"
  assert first_row["values"][0]["periodType"] == "annual"
  assert first_row["values"][0]["referenceNo"] == "20240000000123"

  # ensure quarter data is also included
  quarterly_rows = [
    row for row in statement["rows"] if any(val["periodType"] == "quarter" for val in row["values"])
  ]
  assert quarterly_rows, "quarterly values should be present for comparison"
