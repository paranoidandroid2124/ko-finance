import logging

from scripts._path import add_root

add_root()

from database import Base, engine
from models.fact import ExtractedFact  # noqa: F401
from models.filing import Filing  # noqa: F401
from models.summary import Summary  # noqa: F401
from scripts.migrate_schema import migrate_schema

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def init_db() -> None:
    logger.info("데이터베이스 테이블 생성을 시작합니다...")
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("데이터베이스 테이블이 성공적으로 생성되었습니다.")
        migrate_schema()
    except Exception as exc:
        logger.error("테이블 생성 또는 마이그레이션 중 오류 발생: %s", exc, exc_info=True)


if __name__ == "__main__":
    init_db()
