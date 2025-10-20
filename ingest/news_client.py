
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any

from schemas.news import NewsArticleCreate

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# SSoT(M2)에 기반한 목업 뉴스 데이터.
# 실제 구현 시에는 빅카인즈/라이선스 뉴스 API를 통해 가져옵니다.
MOCK_NEWS_DATABASE: List[Dict[str, Any]] = [
    {
        "ticker": "005930",
        "source": "연합뉴스",
        "url": "https://example.com/news/1",
        "headline": "삼성전자, 4분기 실적 예상치 하회... 반도체 업황 부진 영향",
        "original_text": "삼성전자가 4분기 연결 기준 매출 67조원, 영업이익 2조8000억원을 기록했다고 잠정 발표했다. 이는 시장 예상치를 밑도는 수치로, 글로벌 경기 침체에 따른 반도체 수요 감소가 주된 원인으로 분석된다.",
        "published_at": datetime.now() - timedelta(hours=1),
    },
    {
        "ticker": "000660",
        "source": "매일경제",
        "url": "https://example.com/news/2",
        "headline": "SK하이닉스, AI 메모리 HBM3E 양산 본격화... 엔비디아에 공급",
        "original_text": "SK하이닉스가 인공지능(AI) 서버용 차세대 D램인 HBM3E의 양산을 시작했다고 밝혔다. 초기 물량은 주요 고객사인 엔비디아에 공급될 예정이며, AI 시장 주도권을 강화할 전략이다.",
        "published_at": datetime.now() - timedelta(hours=3),
    },
    {
        "ticker": None, # 특정 종목과 무관한 매크로 뉴스
        "source": "한국은행",
        "url": "https://example.com/news/3",
        "headline": "한국은행, 기준금리 3.50%로 동결... 추가 인상 가능성 시사",
        "original_text": "한국은행 금융통화위원회가 기준금리를 현 수준인 연 3.50%로 유지하기로 결정했다. 다만, 물가 상승 압력이 여전히 높아 향후 추가 금리 인상의 가능성은 열어두었다.",
        "published_at": datetime.now() - timedelta(days=1),
    },
    {
        "ticker": "051910",
        "source": "이데일리",
        "url": "https://example.com/news/4",
        "headline": "LG화학, 미국에 양극재 공장 증설... 1조원 규모 투자",
        "original_text": "LG화학이 미국 테네시주에 연산 6만톤 규모의 양극재 공장을 추가로 증설한다고 발표했다. 총 투자 규모는 약 1조원으로, 북미 전기차 배터리 시장 공략을 가속화할 계획이다.",
        "published_at": datetime.now() - timedelta(hours=8),
    },
]

class MockNewsClient:
    """합법적인 뉴스 소스 API를 모방하는 목업 클라이언트"""

    def __init__(self):
        logger.info("목업 뉴스 클라이언트가 초기화되었습니다.")

    def fetch_news(
        self, 
        query: str = "", 
        tickers: List[str] = None,
        limit: int = 10
    ) -> List[NewsArticleCreate]:
        """
        저장된 목업 데이터베이스에서 뉴스 기사를 필터링하여 가져옵니다.
        실제 클라이언트의 API 시그니처를 모방합니다.
        """
        logger.info(f"목업 뉴스 조회 시작 (쿼리: '{query}', 종목: {tickers})")
        
        results = []
        for article_data in MOCK_NEWS_DATABASE:
            # 티커 필터링
            if tickers and article_data.get("ticker") not in tickers:
                continue
            
            # 쿼리 필터링 (헤드라인 또는 본문 내용)
            if query and (query.lower() not in article_data["headline"].lower() and query.lower() not in article_data["original_text"].lower()):
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
