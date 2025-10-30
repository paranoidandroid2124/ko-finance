/**
 * 휴리스틱 기반 토큰 추정기
 * Zero dependency로 텍스트의 토큰 수를 추정합니다.
 * 한국어, 영어, 코드가 혼합된 토스페이먼츠 문서에 최적화되어 있습니다.
 */
export class TokenEstimator {
  // 기본 문자당 토큰 비율 (평균적으로 문자 1개당 0.75 토큰)
  private static readonly CHAR_TO_TOKEN_RATIO = 0.75;

  // 한국어 가중치 (한국어는 토큰 비율이 높음)
  private static readonly KOREAN_WEIGHT = 0.8;

  // 코드 블록 비율 (코드는 토큰 효율이 좋음)
  private static readonly CODE_BLOCK_RATIO = 0.3;

  // URL당 평균 토큰 수
  private static readonly URL_TOKENS = 8;

  // 인라인 코드 가중치
  private static readonly INLINE_CODE_RATIO = 0.4;

  /**
   * 텍스트의 토큰 수를 추정합니다.
   * @param text 토큰 수를 추정할 텍스트
   * @returns 추정된 토큰 수
   */
  static estimate(text: string): number {
    if (!text || text.length === 0) return 0;

    // 기본 문자 수 기반 추정
    let estimate = text.length * this.CHAR_TO_TOKEN_RATIO;

    // 한국어 문자 가중치 적용
    estimate += this.calculateKoreanWeight(text);

    // 코드 블록 최적화
    estimate += this.calculateCodeBlockWeight(text);

    // 인라인 코드 최적화
    estimate += this.calculateInlineCodeWeight(text);

    // URL 가중치 적용
    estimate += this.calculateUrlWeight(text);

    // 마크다운 헤더 가중치 (헤더는 보통 짧지만 중요)
    estimate += this.calculateHeaderWeight(text);

    return Math.ceil(Math.max(estimate, 1)); // 최소 1 토큰
  }

  /**
   * 한국어 문자에 대한 가중치 계산
   */
  private static calculateKoreanWeight(text: string): number {
    const koreanChars = (text.match(/[ㄱ-ㅎ|ㅏ-ㅣ|가-힣]/g) || []).length;
    return koreanChars * this.KOREAN_WEIGHT;
  }

  /**
   * 코드 블록에 대한 가중치 계산 (토큰 효율이 좋음)
   */
  private static calculateCodeBlockWeight(text: string): number {
    const codeBlocks = text.match(/```[\s\S]*?```/g) || [];
    let adjustment = 0;

    for (const block of codeBlocks) {
      // 코드 블록은 일반 텍스트보다 토큰 효율이 좋음
      const normalEstimate = block.length * this.CHAR_TO_TOKEN_RATIO;
      const codeEstimate = block.length * this.CODE_BLOCK_RATIO;
      adjustment += codeEstimate - normalEstimate;
    }

    return adjustment;
  }

  /**
   * 인라인 코드에 대한 가중치 계산
   */
  private static calculateInlineCodeWeight(text: string): number {
    // 코드 블록을 제거한 후 인라인 코드 찾기
    const withoutCodeBlocks = text.replace(/```[\s\S]*?```/g, "");
    const inlineCodes = withoutCodeBlocks.match(/`[^`]+`/g) || [];

    let adjustment = 0;
    for (const code of inlineCodes) {
      const normalEstimate = code.length * this.CHAR_TO_TOKEN_RATIO;
      const codeEstimate = code.length * this.INLINE_CODE_RATIO;
      adjustment += codeEstimate - normalEstimate;
    }

    return adjustment;
  }

  /**
   * URL에 대한 가중치 계산
   */
  private static calculateUrlWeight(text: string): number {
    const urls = text.match(/https?:\/\/[^\s]+/g) || [];
    let adjustment = 0;

    for (const url of urls) {
      // URL은 일반적으로 많은 토큰을 차지하므로 추가 가중치 적용
      const normalEstimate = url.length * this.CHAR_TO_TOKEN_RATIO;
      const urlEstimate = Math.max(this.URL_TOKENS, normalEstimate);
      adjustment += urlEstimate - normalEstimate;
    }

    return adjustment;
  }

  /**
   * 마크다운 헤더에 대한 가중치 계산
   */
  private static calculateHeaderWeight(text: string): number {
    const headers = text.match(/^#{1,6}\s+.+$/gm) || [];
    // 헤더는 보통 중요한 키워드가 포함되어 있어 약간의 가중치 추가
    return headers.length * 2;
  }

  /**
   * 여러 텍스트의 총 토큰 수를 계산합니다.
   * @param texts 토큰 수를 계산할 텍스트 배열
   * @returns 총 토큰 수
   */
  static estimateTotal(texts: string[]): number {
    return texts.reduce((total, text) => total + this.estimate(text), 0);
  }

  /**
   * 텍스트가 주어진 토큰 한계를 초과하는지 확인합니다.
   * @param text 확인할 텍스트
   * @param maxTokens 최대 토큰 수
   * @returns 초과 여부
   */
  static exceedsLimit(text: string, maxTokens: number): boolean {
    return this.estimate(text) > maxTokens;
  }
}
