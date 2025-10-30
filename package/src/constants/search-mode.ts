export enum SearchMode {
  BROAD = "broad",
  BALANCED = "balanced",
  PRECISE = "precise",
}

export type Bm25Config = {
  k1: number;
  b: number;
};

export const BM25_CONFIGS: Record<SearchMode, Bm25Config> = {
  broad: {
    k1: 1.0, // 낮은 k1 = 용어 빈도에 덜 민감
    b: 0.5, // 낮은 b = 문서 길이에 덜 민감
  },
  balanced: {
    k1: 1.2, // 표준 BM25 값
    b: 0.75, // 표준 BM25 값
  },
  precise: {
    k1: 1.5, // 높은 k1 = 용어 빈도에 더 민감
    b: 0.9, // 높은 b = 문서 길이에 더 민감
  },
};

export const MIN_SCORE_RATIO = {
  broad: 0.1,
  balanced: 0.5,
  precise: 1.0,
};
