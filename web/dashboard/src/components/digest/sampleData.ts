import type { DigestPayload } from "./DigestCard";

export const sampleDigest: DigestPayload = {
  timeframe: "weekly",
  periodLabel: "2025년 11월 6일 · 1주 하이라이트",
  generatedAtLabel: "2025-11-06 10:45 (Asia/Seoul)",
  sourceLabel: "공시 · 뉴스 · 시장지표",
  llmOverview:
    "이번 주에는 반도체와 2차전지 모멘텀이 동시에 강화되며 모멘텀 섹터가 주도했습니다.\nLG에너지솔루션 계약 발표를 제외하면 감성 리스크는 제한적이었지만, NAVER처럼 거래량 급증 신호는 계속 관찰됐습니다.",
  llmPersonalNote:
    "최근 3일간 감시 중인 삼성전자·NAVER에서 거래량 급증 신호가 연속 발생했습니다. 지난주에 설정한 NAVER 리스크 룰을 유지하면서, 다음 구간에서는 2차전지 수주 뉴스에 추가 반응이 나오는지 확인해보세요.",
  news: [
    {
      headline: "삼성전자, 신공정 투자 계획 발표",
      summary: "평택에 20조원 규모의 차세대 반도체 라인 증설 계획을 공개했습니다.",
      source: "전자신문",
      link: "https://example.com/news/samsung-investment",
    },
    {
      headline: "코스피, 외국인 매수세에 2% 상승",
      summary: "미 금리 동결 기대감에 차익 실현이 줄어들며 주요 제조업 섹터가 상승했습니다.",
      source: "연합인포맥스",
    },
    {
      headline: "LG에너지솔루션, 북미 전기차 업체와 공급 계약",
      summary: "고객사명은 비공개이나 5년간 ESS용 배터리 공급 계약을 체결했다고 밝혔습니다.",
      source: "Bloomberg",
    },
  ],
  watchlist: [
    {
      title: "SAMSUNG ELECTRONICS",
      description: "가격이 ₩75,000을 돌파했습니다. 3거래일 연속 상승 구간입니다.",
      changeLabel: "+2.3%",
      tone: "positive",
    },
    {
      title: "NAVER",
      description: "거래량 급증 알림: 전일 대비 180% 증가, AI 플랫폼 부문 리포트 영향.",
      changeLabel: "주의",
      tone: "alert",
    },
    {
      title: "현대차",
      description: "주요 생산라인 점검 소식으로 가격이 ₩189,000 아래로 하락했습니다.",
      changeLabel: "-1.8%",
      tone: "negative",
    },
  ],
  sentiment: {
    summary: "기반 시장 심리는 안정 영역을 유지하고 있습니다.",
    scoreLabel: "72/100",
    trend: "up",
    indicators: [
      { name: "RSI", value: "58.3", status: "neutral" },
      { name: "돌파 감지", value: "12건", status: "positive" },
      { name: "변동성", value: "Low", status: "positive" },
    ],
  },
  actions: [
    {
      title: "반도체 워치리스트 확장",
      note: "최근 7일간 AI·HPC 테마 기업에서 신규 호재가 집중되고 있습니다.",
      tone: "positive",
    },
    {
      title: "NAVER 주간 리스크 점검",
      note: "거래량 급증 배경이 일회성인지 모니터링하고 필요시 알림 한도를 상향하세요.",
      tone: "neutral",
    },
  ],
};

export const emptyDigest: DigestPayload = {
  timeframe: "daily",
  periodLabel: "2025년 11월 7일 · 오늘의 다이제스트",
  generatedAtLabel: "2025-11-07 08:00 (Asia/Seoul)",
  sourceLabel: "공시 · 뉴스 · 시장지표",
  news: [],
  watchlist: [],
  sentiment: null,
  actions: [],
};
