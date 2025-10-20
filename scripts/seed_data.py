import argparse
import logging

from database import SessionLocal
from ingest.dart_seed import seed_recent_filings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="최근 DART 공시를 시딩하고 Celery 파이프라인을 실행합니다.")
    parser.add_argument(
        "--days-back",
        type=int,
        default=1,
        help="조회할 일수(오늘 기준). 기본값 1",
    )
    args = parser.parse_args()

    db_session = SessionLocal()
    try:
        count = seed_recent_filings(days_back=args.days_back, db=db_session)
        logger.info("시딩 완료: 총 %s건의 새 공시 처리 요청.", count)
    finally:
        db_session.close()


if __name__ == "__main__":
    main()
