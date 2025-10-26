export const CHAT_STRINGS = {
  greeting: "안녕하세요! 궁금한 공시나 뉴스가 있으면 편하게 질문해 주세요.",
  newSessionGreeting: (title: string) => `${title} 공시에 대해 어떤 점이 궁금한가요?`
};

export const PDF_STRINGS = {
  loading: "PDF를 준비하는 중입니다.",
  empty: "선택된 근거에 연결된 하이라이트가 없습니다. 근거 패널에서 다른 항목을 선택해 보세요.",
  error: "guardrail이 활성화되었거나 PDF 소스가 준비되지 않았습니다. 잠시 후 다시 시도해 주세요.",
  emptyHint: "하이라이트가 준비되지 않았습니다.",
  errorHint: "PDF 상태 경고",
  overlayLabel: "세부 지표 하이라이트 영역",
  listButton: (summary: string, percentage: number, page: number) =>
    `${summary} (페이지 ${page}, 영역 ${percentage}%)`
};
