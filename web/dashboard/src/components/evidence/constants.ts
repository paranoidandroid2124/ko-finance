"use client";

import type { EvidenceItem, EvidenceSelfCheck } from "./types";

type Reliability = NonNullable<EvidenceItem["sourceReliability"]>;
type DiffType = NonNullable<Exclude<EvidenceItem["diffType"], null | undefined>>;
type Verdict = NonNullable<EvidenceSelfCheck["verdict"]>;

export const RELIABILITY_TONE: Record<Reliability, { badge: string; label: string }> = {
  high: {
    badge:
      "border-emerald-400 bg-emerald-500/10 text-emerald-600 dark:border-emerald-300/40 dark:bg-emerald-500/10 dark:text-emerald-200",
    label: "신뢰도 높아요",
  },
  medium: {
    badge:
      "border-amber-400 bg-amber-500/10 text-amber-600 dark:border-amber-300/40 dark:bg-amber-500/10 dark:text-amber-100",
    label: "신뢰도 보통이에요",
  },
  low: {
    badge:
      "border-destructive/60 bg-destructive/10 text-destructive dark:border-destructive/60 dark:bg-destructive/15 dark:text-destructive",
    label: "신뢰도 낮은 편이에요",
  },
};

export const VERDICT_TONE: Record<Verdict, { badge: string; label: string }> = {
  pass: {
    badge:
      "border-emerald-400 bg-emerald-500/10 text-emerald-600 dark:border-emerald-300/40 dark:bg-emerald-500/10 dark:text-emerald-200",
    label: "셀프 체크 통과",
  },
  warn: {
    badge:
      "border-amber-400 bg-amber-500/10 text-amber-600 dark:border-amber-300/40 dark:bg-amber-500/10 dark:text-amber-100",
    label: "셀프 체크 주의",
  },
  fail: {
    badge:
      "border-destructive/60 bg-destructive/10 text-destructive dark:border-destructive/60 dark:bg-destructive/15 dark:text-destructive",
    label: "셀프 체크 다시 보기",
  },
};

export const DIFF_TONE: Record<DiffType, { badge: string; label: string; card: string; quote: string }> = {
  created: {
    badge:
      "border-emerald-400 bg-emerald-500/10 text-emerald-600 dark:border-emerald-300/40 dark:bg-emerald-500/10 dark:text-emerald-200",
    label: "새로 담겼어요",
    card: "border-emerald-400/50 bg-emerald-50/40 dark:border-emerald-300/40 dark:bg-emerald-500/10",
    quote: "border-emerald-300/60 bg-emerald-500/10 text-emerald-700 dark:border-emerald-300/40 dark:text-emerald-200",
  },
  updated: {
    badge:
      "border-sky-400 bg-sky-500/10 text-sky-700 dark:border-sky-300/40 dark:bg-sky-500/10 dark:text-sky-200",
    label: "내용이 바뀌었어요",
    card: "border-sky-400/60 bg-sky-50/30 dark:border-sky-300/40 dark:bg-sky-500/10",
    quote: "border-sky-300/60 bg-sky-500/10 text-sky-700 dark:border-sky-300/40 dark:text-sky-200",
  },
  unchanged: {
    badge:
      "border-border-light bg-background-cardLight text-text-tertiaryLight dark:border-border-dark dark:bg-white/5 dark:text-text-tertiaryDark",
    label: "변화 없어요",
    card: "opacity-90",
    quote: "text-text-secondaryLight dark:text-text-secondaryDark",
  },
  removed: {
    badge:
      "border-destructive/60 bg-destructive/10 text-destructive dark:border-destructive/60 dark:bg-destructive/15 dark:text-destructive",
    label: "이젠 빠졌어요",
    card: "border-destructive/60 bg-destructive/5 dark:border-destructive/70 dark:bg-destructive/20",
    quote: "border-destructive/60 bg-destructive/10 text-destructive dark:text-destructive",
  },
};

export const DIFF_FIELD_LABELS: Record<string, string> = {
  quote: "문장",
  section: "섹션",
  page_number: "페이지",
  pageNumber: "페이지",
  anchor: "하이라이트 위치",
  source_reliability: "출처 신뢰도",
  sourceReliability: "출처 신뢰도",
  self_check: "셀프 체크",
  selfCheck: "셀프 체크",
};

