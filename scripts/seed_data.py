import argparse
import logging
from datetime import date, datetime

from scripts._path import add_root

add_root()

from database import SessionLocal
from ingest.dart_seed import seed_recent_filings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()


def main() -> None:
    parser = argparse.ArgumentParser(description="최근 DART 공시를 시드하고 Celery 파이프라인을 트리거합니다.")
    parser.add_argument(
        "--days-back",
        type=int,
        default=1,
        help="조회할 일수(오늘 기준). 기본값 1",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        help="조회 시작 일자 (YYYY-MM-DD). 지정 시 --days-back보다 우선합니다.",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        help="조회 종료 일자 (YYYY-MM-DD). 기본은 오늘.",
    )
    parser.add_argument(
        "--corp-code",
        type=str,
        help="특정 기업의 공시만 조회할 DART 법인코드(8자리).",
    )
    args = parser.parse_args()

    start_date = _parse_date(args.start_date)
    end_date = _parse_date(args.end_date)

    db_session = SessionLocal()
    try:
        count = seed_recent_filings(
            days_back=args.days_back,
            db=db_session,
            start_date=start_date,
            end_date=end_date,
            corp_code=args.corp_code,
        )
        logger.info("시딩 완료: 총 %s건의 새 공시 처리 요청.", count)
    finally:
        db_session.close()


if __name__ == "__main__":
    main()
