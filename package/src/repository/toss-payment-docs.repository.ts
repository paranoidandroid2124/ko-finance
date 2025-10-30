import { SearchMode } from "../constants/search-mode.js";
import { CategoryWeightCalculator } from "../document/category-weight-calculator.js";
import {
  Result,
  TossPaymentsBM25Calculator,
} from "../document/toss-payments-bm25-calculator.js";
import { TossPaymentsDocument } from "../document/toss-payments-document.js";

import { SynonymDictionary } from "../document/synonym-dictionary.js";
import { TokenEstimator } from "../document/token-estimator.js";
import { DocumentChunk } from "../document/types.js";

export class TossPaymentDocsRepository {
  private readonly documentV1BM25Calculator: TossPaymentsBM25Calculator;
  private readonly documentV2BM25Calculator: TossPaymentsBM25Calculator;

  private readonly allV1Keywords: Set<string>;
  private readonly allV2Keywords: Set<string>;

  private static readonly TRUNCATION_WARNING =
    "\n\n... (내용이 더 있습니다...)";

  constructor(
    private readonly documents: TossPaymentsDocument[],
    private readonly categoryWeightCalculator: CategoryWeightCalculator,
    private readonly synonymDictionary: SynonymDictionary
  ) {
    const v1Documents = documents.filter(
      (document) => document.version === "v1"
    );

    const v2Documents = documents.filter(
      (document) => document.version === "v2"
    );

    this.documentV1BM25Calculator = new TossPaymentsBM25Calculator(v1Documents);
    this.documentV2BM25Calculator = new TossPaymentsBM25Calculator(v2Documents);

    this.allV2Keywords = new Set(v1Documents.map((doc) => doc.keywords).flat());
    this.allV1Keywords = new Set(v2Documents.map((doc) => doc.keywords).flat());
  }

  getAllV1Keywords(): string[] {
    return Array.from(this.allV1Keywords);
  }

  getAllV2Keywords(): string[] {
    return Array.from(this.allV2Keywords);
  }

  async findV1DocumentsByKeyword(
    keywords: string[],
    searchMode: SearchMode = SearchMode.BALANCED,
    maxTokens: number
  ): Promise<string> {
    const converted = this.synonymDictionary.convertToSynonyms(keywords);

    const results = this.documentV1BM25Calculator.calculate(
      converted,
      searchMode
    );

    // Category별 가중치 적용
    const weightedResults = this.categoryWeightCalculator.apply(
      results,
      this.documents
    );

    return this.normalize(weightedResults, maxTokens);
  }

  async findV2DocumentsByKeyword(
    keywords: string[],
    searchMode: SearchMode = SearchMode.BALANCED,
    maxTokens: number
  ): Promise<string> {
    const converted = this.synonymDictionary.convertToSynonyms(keywords);

    const results = this.documentV2BM25Calculator.calculate(
      converted,
      searchMode
    );

    // Category별 가중치 적용
    const weightedResults = this.categoryWeightCalculator.apply(
      results,
      this.documents
    );

    return this.normalize(weightedResults, maxTokens);
  }

  findOneById(id: number) {
    return this.documents[id];
  }

  private normalize(results: Result[], maxTokens: number): string {
    const groupedByDocId = this.groupResultsByDocId(results);
    const docs: string[] = [];
    let currentTokens = 0;

    // 각 문서별로 chunk 조회
    for (const [docId, chunkIds] of groupedByDocId.entries()) {
      const document = this.findOneById(docId);

      const documentChunks = document.findByChunkIds(chunkIds, {
        windowSize: 1,
      });

      if (documentChunks.length > 0) {
        const processedChunk = this.smartTruncateChunks(
          documentChunks,
          maxTokens - currentTokens
        );

        if (processedChunk) {
          const header = `# 원본문서 제목 : ${document.title}\n* 원본문서 ID : ${document.id}`;

          const headerTokens = TokenEstimator.estimate(header);

          maxTokens -= headerTokens;

          docs.push(header);
          docs.push(processedChunk.text);
          currentTokens += processedChunk.tokens;

          if (currentTokens >= maxTokens) {
            break;
          }
        }
      }
    }

    return docs.join("\n\n");
  }

  /**
   * Result 배열을 문서 ID별로 그룹핑
   */
  private groupResultsByDocId(results: Result[]): Map<number, number[]> {
    const grouped = new Map<number, number[]>();

    for (const result of results) {
      if (!grouped.has(result.id)) {
        grouped.set(result.id, []);
      }
      grouped.get(result.id)!.push(result.chunkId);
    }

    // 각 그룹의 chunkId를 중복 제거 및 정렬
    for (const [docId, chunkIds] of grouped.entries()) {
      grouped.set(
        docId,
        [...new Set(chunkIds)].sort((a, b) => a - b)
      );
    }

    return grouped;
  }

  /**
   * 토큰 제한 하에서 chunks를 스마트하게 절단합니다.
   * @param chunks 처리할 DocumentChunk 배열
   * @param remainingTokens 남은 토큰 수
   * @returns 처리된 텍스트와 사용된 토큰 수
   */
  private smartTruncateChunks(
    chunks: DocumentChunk[],
    remainingTokens: number
  ): { text: string; tokens: number } | null {
    if (chunks.length === 0) return null;

    let availableTokens = remainingTokens;
    if (availableTokens <= 0) return null;

    let selectedChunks: DocumentChunk[] = [];
    let usedTokens = 0;

    // chunk별 토큰 수를 확인하면서 선택
    for (const chunk of chunks) {
      const chunkTokens = chunk.estimatedTokens;

      if (availableTokens >= chunkTokens) {
        selectedChunks.push(chunk);
        availableTokens -= chunkTokens;
        usedTokens += chunkTokens;
      } else {
        // 부분 선택 가능한지 확인
        const partialChunk = this.tryPartialChunk(chunk, availableTokens);
        if (partialChunk) {
          selectedChunks.push(partialChunk.chunk);
          usedTokens += partialChunk.tokens;
        }
        break;
      }
    }

    if (selectedChunks.length === 0) {
      return null;
    }

    const needsTruncation = selectedChunks.length < chunks.length;
    const content = selectedChunks.map((chunk) => chunk.rawText).join("\n\n");
    const fullText =
      content +
      (needsTruncation ? TossPaymentDocsRepository.TRUNCATION_WARNING : "");

    const finalTokens =
      usedTokens +
      (needsTruncation
        ? TokenEstimator.estimate(TossPaymentDocsRepository.TRUNCATION_WARNING)
        : 0);

    return {
      text: fullText,
      tokens: finalTokens,
    };
  }

  /**
   * 토큰 제한 하에서 chunk를 부분적으로 절단을 시도합니다.
   * @param chunk 절단할 DocumentChunk
   * @param availableTokens 사용 가능한 토큰 수
   * @returns 부분 절단된 chunk와 토큰 수
   */
  private tryPartialChunk(
    chunk: DocumentChunk,
    availableTokens: number
  ): { chunk: DocumentChunk; tokens: number } | null {
    if (availableTokens < 100) return null; // 최소한의 토큰은 필요

    // 의미 단위로 자르기 시도 (문장, 단락, 리스트 아이템 등)
    const semanticBoundaries = this.findSemanticBoundaries(chunk.text);

    for (let i = semanticBoundaries.length - 1; i >= 0; i--) {
      const truncatedText = chunk.text.substring(0, semanticBoundaries[i]);
      const estimatedTokens = TokenEstimator.estimate(truncatedText);

      if (estimatedTokens <= availableTokens) {
        return {
          chunk: { ...chunk, text: truncatedText },
          tokens: estimatedTokens,
        };
      }
    }

    return null;
  }

  /**
   * 텍스트에서 의미 있는 경계점들을 찾습니다.
   * @param text 분석할 텍스트
   * @returns 경계점 위치 배열 (문자 인덱스)
   */
  private findSemanticBoundaries(text: string): number[] {
    const boundaries: number[] = [];

    // 1. 문단 경계 (더블 개행)
    let match;
    const paragraphRegex = /\n\n/g;
    while ((match = paragraphRegex.exec(text)) !== null) {
      boundaries.push(match.index);
    }

    // 2. 문장 경계 (마침표, 느낌표, 물음표 + 공백)
    const sentenceRegex = /[.!?]\s+/g;
    while ((match = sentenceRegex.exec(text)) !== null) {
      boundaries.push(match.index + match[0].length);
    }

    // 3. 리스트 아이템 경계
    const listRegex = /\n-\s+/g;
    while ((match = listRegex.exec(text)) !== null) {
      boundaries.push(match.index);
    }

    // 4. 코드 블록 경계
    const codeBlockRegex = /```[\s\S]*?```/g;
    while ((match = codeBlockRegex.exec(text)) !== null) {
      boundaries.push(match.index + match[0].length);
    }

    // 정렬 및 중복 제거
    return [...new Set(boundaries)].sort((a, b) => a - b);
  }
}
