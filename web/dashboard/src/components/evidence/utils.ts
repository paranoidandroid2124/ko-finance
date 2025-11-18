"use client";

import type { EvidenceAnchor } from "./types";

export function formatSimilarity(anchor?: EvidenceAnchor | null): string | null {
  if (!anchor || anchor.similarity === undefined || anchor.similarity === null) {
    return null;
  }
  return `${Math.round(anchor.similarity * 100)}% 일치`;
}

