export class SynonymDictionary {
  private readonly dictionary: Record<string, string[]> = {
    결제취소: ["결제 취소"],
    부분취소: ["부분 취소"],
    환불정책: ["환불", "정책", "규정"],
    결제한도: ["결제", "한도", "제한"],
    결제만료: ["결제", "만료"],
    "결제 만료": ["결제", "만료"],
    가상계좌만료: ["가상계좌", "만료"],
    정산주기: ["정산", "주기", "기간"],
    "정산 주기": ["정산", "주기", "기간"],
    정산지연: ["정산", "지연"],
    "정산 지연": ["정산", "지연"],
    정산오류: ["정산", "오류"],
    "정산 오류": ["정산", "오류"],
    무이자할부: ["무이자", "할부"],
    "무이자 할부": ["무이자", "할부"],
    카드사부담무이할부: ["카드사", "부담", "무이자 할부"],
    카드사무이자할부: ["카드사", "무이자 할부"],
    카드사부분무이자할부: ["카드사", "부분", "무이자 할부"],
    "카드사 무이자 할부": ["카드사", "무이자 할부"],
    부분무이자할부: ["부분", "무이자 할부"],
    "부분 무이자 할부": ["부분", "무이자 할부"],
    "부분무이자 할부": ["부분", "무이자 할부"],
    "부분 무이자할부": ["부분", "무이자 할부"],
    가상계좌발급: ["가상계좌 발급"],
    "결제 위젯": ["결제위젯", "위젯"],
    메서드: ["method", "함수"],
    JavaScriptSDK: ["JavaScript SDK", "JavaScript", "SDK"],
  };

  getSynonyms(term: string): string[] {
    return this.dictionary[term] || [];
  }

  convertToSynonyms(terms: string[]): string[] {
    const synonyms: string[] = [];
    for (const term of terms) {
      const termSynonyms = this.getSynonyms(term);
      if (termSynonyms.length > 0) {
        synonyms.push(...termSynonyms);
      } else {
        synonyms.push(term);
      }
    }
    return synonyms;
  }
}
