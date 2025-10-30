export type Category =
  | "blog"
  | "codes"
  | "guides"
  | "resources"
  | "reference"
  | "sdk"
  | "legacy"
  | "unknown";

export const categories: Category[] = [
  "blog",
  "codes",
  "guides",
  "resources",
  "reference",
  "sdk",
  "legacy",
  "unknown",
] as const;

const set = new Set<string>(categories);

export function isCategory(value: string): value is Category {
  return set.has(value);
}

/**
 * Category별 가중치 설정
 * 1.0 = 기본값, 0.5 = 50% 감소, 1.2 = 20% 증가
 */
export const CATEGORY_WEIGHTS: Record<Category, number> = {
  guides: 1.2, // 가이드 문서 우선순위 높임
  reference: 1.0, // 레퍼런스 문서 기본값
  sdk: 1.0, // SDK 문서 기본값 (reference와 동일)
  resources: 0.8, // 리소스 문서 약간 낮춤
  blog: 0.7, // 블로그 포스트 낮춤
  codes: 0.5, // 에러코드/벤더사/enum 정보 많이 낮춤
  legacy: 0.4, // 레거시 문서 많이 낮춤
  unknown: 1.0,
} as const;
