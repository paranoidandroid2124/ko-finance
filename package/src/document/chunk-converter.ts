import { EnhancedChunk } from "./splitter/types.js";
import { TokenEstimator } from "./token-estimator.js";
import { DocumentChunk, DocumentMetadata } from "./types.js";

/**
 * EnhancedChunk를 DocumentChunk로 변환하는 유틸리티
 * 컨텍스트 정보를 포함한 최종 chunk를 생성합니다.
 */
export class ChunkConverter {
  /**
   * EnhancedChunk를 DocumentChunk로 변환합니다.
   * @param enhancedChunk 변환할 EnhancedChunk
   * @param metadata 문서 메타데이터
   * @param documentId 문서 ID
   * @param chunkIndex chunk 인덱스
   * @returns 컨텍스트가 포함된 DocumentChunk
   */
  static convert(
    enhancedChunk: EnhancedChunk,
    metadata: DocumentMetadata,
    documentId: number,
    chunkIndex: number
  ): DocumentChunk {
    // 컨텍스트 프리픽스 생성
    const contextPrefix = this.buildContextPrefix(
      metadata,
      enhancedChunk.headerStack
    );

    // 컨텍스트 포함 전체 텍스트
    const fullText = contextPrefix + enhancedChunk.content;

    // 컨텍스트 포함 토큰 수 계산
    const fullTokens = TokenEstimator.estimate(fullText);

    return {
      id: documentId,
      chunkId: chunkIndex,
      originTitle: metadata.title,
      text: fullText,
      rawText: enhancedChunk.content,
      wordCount: fullText.split(/\s+/).length,
      estimatedTokens: fullTokens,
      headerStack: [...enhancedChunk.headerStack], // 복사본 생성
    };
  }

  /**
   * 여러 EnhancedChunk를 DocumentChunk 배열로 변환합니다.
   * @param enhancedChunks 변환할 EnhancedChunk 배열
   * @param metadata 문서 메타데이터
   * @param documentId 문서 ID
   * @returns DocumentChunk 배열
   */
  static convertAll(
    enhancedChunks: EnhancedChunk[],
    metadata: DocumentMetadata,
    documentId: number
  ): DocumentChunk[] {
    return enhancedChunks.map((chunk, index) =>
      this.convert(chunk, metadata, documentId, index)
    );
  }

  /**
   * 컨텍스트 프리픽스를 생성합니다.
   * @param metadata 문서 메타데이터
   * @param headerStack 헤더 경로
   * @returns 컨텍스트 프리픽스 문자열
   */
  private static buildContextPrefix(
    metadata: DocumentMetadata,
    headerStack: string[]
  ): string {
    const headerPath = headerStack.filter((h) => h && h.trim()).join(" > ");
    const keywordList = metadata.keyword.join(", "); // 문서 메타데이터의 키워드 사용

    let contextPrefix = `## Metadata \n`;

    if (keywordList) {
      contextPrefix += `Keywords: ${keywordList}\n`;
    }

    if (headerPath) {
      contextPrefix += `Header Path: ${headerPath}\n`;
    }

    contextPrefix += "\n";

    return contextPrefix;
  }

  /**
   * 컨텍스트 없이 순수 내용만 포함된 DocumentChunk를 생성합니다.
   * (응답 생성 시 스마트 절단에서 사용)
   * @param enhancedChunk 변환할 EnhancedChunk
   * @param metadata 문서 메타데이터
   * @param documentId 문서 ID
   * @param chunkIndex chunk 인덱스
   * @returns 순수 내용만 포함된 DocumentChunk
   */
  static convertRaw(
    enhancedChunk: EnhancedChunk,
    metadata: DocumentMetadata,
    documentId: number,
    chunkIndex: number
  ): DocumentChunk {
    return {
      id: documentId,
      chunkId: chunkIndex,
      originTitle: metadata.title,
      text: enhancedChunk.content,
      rawText: enhancedChunk.content,
      wordCount: enhancedChunk.content.split(/\s+/).length,
      estimatedTokens: enhancedChunk.estimatedTokens,
      headerStack: [...enhancedChunk.headerStack],
    };
  }
}
