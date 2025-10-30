import { Category } from "../constants/category.js";
import { ChunkConverter } from "./chunk-converter.js";
import { DocumentChunk, RemoteMarkdownDocument } from "./types.js";

export class TossPaymentsDocument {
  private readonly chunks: DocumentChunk[] = [];

  constructor(
    private readonly keywordSet: Set<string>,
    private readonly remoteMarkdownDocument: RemoteMarkdownDocument,
    private readonly _version: string | undefined,
    public readonly id: number,
    private readonly _category: Category
  ) {
    const convertedChunks = ChunkConverter.convertAll(
      remoteMarkdownDocument.enhancedChunks,
      remoteMarkdownDocument.metadata,
      this.id
    );
    // chunkId를 고유하게 재설정
    convertedChunks.forEach((chunk, index) => {
      chunk.chunkId = this.id * 1000 + index;
      this.chunks.push(chunk);
    });
  }

  /**
   * 여러 chunkId들을 기반으로 최적화된 chunk 배열을 반환
   * 연속적인 chunk들은 통합하고, window를 적용하여 중복을 제거
   */
  findByChunkIds(
    chunkIds: number[],
    options: { windowSize: number } = { windowSize: 1 }
  ): DocumentChunk[] {
    if (chunkIds.length === 0) return [];

    const { windowSize } = options;

    // chunkId를 index로 변환 및 유효성 검증
    const validIndices = chunkIds
      .map((chunkId) => chunkId - this.id * 1000)
      .filter((index) => index >= 0 && index < this.chunks.length)
      .sort((a, b) => a - b);

    if (validIndices.length === 0) return [];

    // 중복 제거
    const uniqueIndices = [...new Set(validIndices)];

    if (uniqueIndices.length === 1) {
      // 단일 chunk인 경우 window 적용
      const chunkIndex = uniqueIndices[0];
      const start = Math.max(0, chunkIndex - windowSize);
      const end = Math.min(this.chunks.length - 1, chunkIndex + windowSize);
      return this.chunks.slice(start, end + 1);
    }

    // 연속성 분석을 위한 그룹 생성
    const groups = this.groupConsecutiveIndices(uniqueIndices, windowSize);

    const result: DocumentChunk[] = [];
    for (const group of groups) {
      const start = Math.max(0, Math.min(...group) - windowSize);
      const end = Math.min(
        this.chunks.length - 1,
        Math.max(...group) + windowSize
      );
      result.push(...this.chunks.slice(start, end + 1));
    }

    // 중복 제거 (chunkId 기준)
    const uniqueChunks = new Map<number, DocumentChunk>();
    for (const chunk of result) {
      uniqueChunks.set(chunk.chunkId, chunk);
    }

    return Array.from(uniqueChunks.values()).sort(
      (a, b) => a.chunkId - b.chunkId
    );
  }

  /**
   * chunk 인덱스들을 연속성과 window 고려하여 그룹핑
   */
  private groupConsecutiveIndices(
    indices: number[],
    windowSize: number
  ): number[][] {
    if (indices.length === 0) return [];

    const groups: number[][] = [];
    let currentGroup = [indices[0]];

    for (let i = 1; i < indices.length; i++) {
      const prev = indices[i - 1];
      const current = indices[i];

      // 현재 index가 이전 index와 연결 가능한지 확인
      // window size를 고려해서 gap이 (windowSize * 2 + 1) 이하면 연결
      const maxGap = windowSize * 2 + 1;
      if (current - prev <= maxGap) {
        currentGroup.push(current);
      } else {
        // 새로운 그룹 시작
        groups.push(currentGroup);
        currentGroup = [current];
      }
    }

    groups.push(currentGroup);
    return groups;
  }

  getChunks(): DocumentChunk[] {
    return this.chunks;
  }

  get keywords(): string[] {
    return Array.from(this.keywordSet);
  }

  get content(): string {
    return this.remoteMarkdownDocument.markdown;
  }

  get title() {
    return this.remoteMarkdownDocument.metadata.title;
  }

  get version(): string | undefined {
    return this._version;
  }

  get category(): Category {
    return this._category;
  }

  get description() {
    return this.remoteMarkdownDocument.metadata.description;
  }

  toString() {
    return this.remoteMarkdownDocument.markdown;
  }

  toJSON() {
    return {
      version: this.version,
      id: this.id,
      title: this.title,
      link: this.remoteMarkdownDocument.link,
      description: this.description,
      keywords: Array.from(this.keywordSet),
    };
  }
}
