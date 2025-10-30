import {
  BM25_CONFIGS,
  Bm25Config,
  MIN_SCORE_RATIO,
  SearchMode,
} from "../constants/search-mode.js";
import { TossPaymentsDocument } from "./toss-payments-document.js";
import { DocumentChunk } from "./types.js";

type Score = { id: number; chunkId: number; score: number; totalTF: number };

export class TossPaymentsBM25Calculator {
  private readonly allChunks: DocumentChunk[];
  private readonly totalCount: number;
  private readonly averageDocLength: number;
  private readonly N: number;

  constructor(documents: TossPaymentsDocument[]) {
    this.allChunks = documents.flatMap((doc) => doc.getChunks());
    this.totalCount = this.allChunks.reduce(
      (count, doc) => count + doc.wordCount,
      0
    );
    this.averageDocLength = this.totalCount / this.allChunks.length;
    this.N = this.allChunks.length;
  }

  calculate(keywords: string[], searchMode: SearchMode): Result[] {
    const regexp = this.createRegexp(keywords);
    const config = BM25_CONFIGS[searchMode];

    const { termFrequencies, docFrequencies } =
      this.calculateFrequencies(regexp);

    const scores = this.calculateScore(termFrequencies, docFrequencies, config);

    scores.sort((a, b) =>
      b.score !== a.score ? b.score - a.score : b.totalTF - a.totalTF
    );

    const filteredScores = this.applyRelativeFilter(scores, searchMode);

    return filteredScores.map(({ id, score, chunkId }) => ({
      id,
      chunkId,
      score,
    }));
  }

  /**
   * 최고 점수 대비 상대적 임계값을 적용하여 필터링
   */
  private applyRelativeFilter(
    scores: Score[],
    searchMode: SearchMode
  ): Score[] {
    const minScoreRatio = MIN_SCORE_RATIO[searchMode];

    if (scores.length === 0) return scores;

    const maxScore = scores[0].score;

    const relativeThreshold = maxScore * this.getThresholdRatio(minScoreRatio);

    const filtered = scores.filter((s) => s.score >= relativeThreshold);

    // 최소 1개는 보장 (최고점수 문서는 항상 포함)
    return filtered.length > 0 ? filtered : [scores[0]];
  }

  /**
   * minScore 값을 상대적 비율로 매핑
   */
  private getThresholdRatio(minScore: number): number {
    // minScore 0.1~1.0 -> 비율 0.05~0.7로 매핑
    return Math.max(0.05, Math.min(0.7, minScore * 0.7));
  }

  private createRegexp(keywords: string[]) {
    const set = new Set(
      keywords.map((keyword) => this.escapeRegExp(keyword.trim()))
    );

    const query = Array.from(set).join("|");

    return new RegExp(query, "gi");
  }

  private calculateFrequencies(regexp: RegExp) {
    const termFrequencies: Record<number, Record<string, number>> = {};
    const docFrequencies: Record<string, number> = {};

    for (const doc of this.allChunks) {
      const text = doc.text;

      const matches = Array.from(text.matchAll(regexp));
      const termCounts: Record<string, number> = {};

      for (const match of matches) {
        const term = match[0].toLowerCase();
        termCounts[term] = (termCounts[term] || 0) + 1;
      }

      if (Object.keys(termCounts).length > 0) {
        termFrequencies[doc.chunkId] = termCounts;
        for (const term of Object.keys(termCounts)) {
          docFrequencies[term] = (docFrequencies[term] || 0) + 1;
        }
      }
    }

    return { termFrequencies, docFrequencies };
  }

  private calculateScore(
    termFrequencies: Record<number, Record<string, number>>,
    docFrequencies: Record<string, number>,
    config: Bm25Config
  ): Score[] {
    return this.allChunks
      .filter((chunk) => termFrequencies[chunk.chunkId])
      .map((chunk) => {
        const tf = termFrequencies[chunk.chunkId];
        const len = chunk.wordCount;

        const score = Object.keys(tf)
          .map((term) => {
            const df = docFrequencies[term];
            const idf = Math.log((this.N - df + 0.5) / (df + 0.5));
            const numerator = tf[term] * (config.k1 + 1);
            const denominator =
              tf[term] +
              config.k1 *
                (1 - config.b + config.b * (len / this.averageDocLength));
            return idf * (numerator / denominator);
          })
          .reduce((sum, v) => sum + v, 0);

        const totalTF = Object.values(tf).reduce((sum, v) => sum + v, 0);

        return {
          id: chunk.id,
          chunkId: chunk.chunkId,
          score,
          totalTF,
        };
      });
  }

  private escapeRegExp(string: string) {
    return string.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"); // $&는 일치한 전체 문자열을 의미합니다.
  }
}

export interface Result {
  id: number;
  chunkId: number;
  score: number;
}
