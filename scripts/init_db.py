import logging
import time
from typing import Callable

from scripts._path import add_root

add_root()

from sqlalchemy.exc import OperationalError

from database import Base, engine
from models.company import CorpMetric, FilingEvent, InsiderTransaction  # noqa: F401
from models.fact import ExtractedFact  # noqa: F401
from models.filing import Filing  # noqa: F401
from models.news import NewsObservation, NewsSignal, NewsWindowAggregate  # noqa: F401
from models.sector import (  # noqa: F401
    NewsArticleSector,
    Sector,
    SectorDailyMetric,
    SectorWindowMetric,
)
from models.summary import Summary  # noqa: F401
from scripts.migrate_schema import migrate_schema

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _retry(operation: Callable[[], None], *, retries: int = 7, delay: float = 3.0) -> None:
    for attempt in range(1, retries + 1):
        try:
            operation()
            return
        except OperationalError as exc:
            if attempt == retries:
                raise
            logger.warning(
                "데이터베이스 연결이 아직 준비되지 않았어요. %d번째 재시도까지 %.1f초 대기합니다. (%s)",
                attempt,
                delay,
                exc,
            )
            time.sleep(delay)


def init_db() -> None:
    logger.info("데이터베이스 초기화를 시작합니다.")
    try:
        _retry(lambda: Base.metadata.create_all(bind=engine))
        logger.info("기본 테이블 생성이 완료됐어요.")
        migrate_schema()
    except Exception as exc:
        logger.error("데이터베이스 초기화 중 오류가 발생했어요: %s", exc, exc_info=True)


if __name__ == "__main__":
    init_db()
