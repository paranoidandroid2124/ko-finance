import { CATEGORY_WEIGHTS, Category } from "../constants/category.js";
import { Result } from "./toss-payments-bm25-calculator.js";
import { TossPaymentsDocument } from "./toss-payments-document.js";

export class CategoryWeightCalculator {
  private readonly weights: Record<Category, number>;

  constructor(customWeights?: Partial<Record<Category, number>>) {
    this.weights = { ...CATEGORY_WEIGHTS, ...customWeights };
  }

  /**
   * BM25 결과에 category별 가중치를 적용하고 재정렬
   */
  apply(results: Result[], documents: TossPaymentsDocument[]): Result[] {
    // 문서 ID별 빠른 조회를 위한 Map 생성
    const documentMap = this.createDocumentMap(documents);

    return results
      .map((result) => {
        const document = documentMap.get(result.id);
        if (!document) {
          console.warn(`Document not found for id: ${result.id}`);
          return result;
        }

        const categoryWeight = this.weights[document.category];

        return {
          ...result,
          score: result.score * categoryWeight,
        };
      })
      .sort((a, b) => b.score - a.score); // 가중치 적용 후 재정렬
  }

  /**
   * 특정 category의 가중치 업데이트
   */
  updateWeight(category: Category, weight: number): void {
    this.weights[category] = weight;
  }

  /**
   * 현재 가중치 설정 조회
   */
  getWeights(): Readonly<Record<Category, number>> {
    return this.weights;
  }

  /**
   * 특정 category의 가중치 조회
   */
  getWeight(category: Category): number {
    return this.weights[category];
  }

  /**
   * 문서 배열을 ID 기반 Map으로 변환 (성능 최적화)
   */
  private createDocumentMap(
    documents: TossPaymentsDocument[]
  ): Map<number, TossPaymentsDocument> {
    const map = new Map<number, TossPaymentsDocument>();
    for (const doc of documents) {
      map.set(doc.id, doc);
    }
    return map;
  }
}
