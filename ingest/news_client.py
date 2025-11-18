
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from schemas.news import NewsArticleCreate

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 혼선을 막기 위해 기본 목업 데이터는 제공하지 않는다.
MOCK_NEWS_DATABASE: List[Dict[str, Any]] = []

class MockNewsClient:
    """합법적인 뉴스 소스 API를 모방하는 목업 클라이언트"""

    def __init__(self):
        logger.info("목업 뉴스 클라이언트가 초기화되었습니다.")

    def fetch_news(
        self,
        query: str = "",
        tickers: Optional[List[str]] = None,
        limit: int = 10,
    ) -> List[NewsArticleCreate]:
        """
        저장된 목업 데이터베이스에서 뉴스 기사를 필터링하여 가져옵니다.
        실제 클라이언트의 API 시그니처를 모방합니다.
        """
        if not MOCK_NEWS_DATABASE:
            logger.warning("목업 뉴스 데이터베이스가 비어 있습니다. 반환할 기사가 없습니다.")
            return []

        logger.info(f"목업 뉴스 조회 시작 (쿼리: '{query}', 종목: {tickers})")

        results = []
        for article_data in MOCK_NEWS_DATABASE:
            if tickers and article_data.get("ticker") not in tickers:
                continue

            if query and (
                query.lower() not in article_data["headline"].lower()
                and query.lower() not in article_data["original_text"].lower()
            ):
                continue

            results.append(NewsArticleCreate(**article_data))

        logger.info(f"{len(results)}개의 목업 뉴스를 반환합니다.")
        return results[:limit]


# 사용 예시
if __name__ == "__main__":
    print("--- 목업 뉴스 클라이언트 테스트 ---")
    client = MockNewsClient()

    print("\n1. 전체 뉴스 조회:")
    all_news = client.fetch_news()
    for news in all_news:
        print(f"- [{news.source}] {news.headline}")

    print("\n2. 'AI' 쿼리로 뉴스 검색:")
    ai_news = client.fetch_news(query="AI")
    for news in ai_news:
        print(f"- [{news.source}] {news.headline}")

    print("\n3. 특정 티커('005930')로 뉴스 조회:")
    samsung_news = client.fetch_news(tickers=["005930"])
    for news in samsung_news:
        print(f"- [{news.source}] {news.headline}")
