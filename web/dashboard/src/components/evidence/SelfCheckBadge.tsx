"use client";

import type { EvidenceSelfCheck } from "./types";
import { VERDICT_TONE } from "./constants";

type Props = {
  value?: EvidenceSelfCheck | null;
};

export function SelfCheckBadge({ value }: Props) {
  if (!value?.verdict) {
    return null;
  }
  const tone = VERDICT_TONE[value.verdict];
  if (!tone) {
    return null;
  }
  return (
    <span className={`inline-flex items-center rounded-md border px-2 py-0.5 text-[11px] font-semibold ${tone.badge}`}>
      {tone.label}
    </span>
  );
}

