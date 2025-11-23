"use client";

import { useCallback, useState } from "react";

type Props = {
  href?: string;
  label?: string;
};

export function CopyLinkButton({ href, label = "링크 복사" }: Props) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(async () => {
    const target = href || (typeof window !== "undefined" ? window.location.href : "");
    if (!target) return;
    try {
      await navigator.clipboard.writeText(target);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch (err) {
      console.error("Failed to copy link", err);
    }
  }, [href]);

  return (
    <button
      type="button"
      onClick={handleCopy}
      className="inline-flex items-center gap-2 rounded-full border border-white/20 px-4 py-2 text-sm font-semibold text-white/90 hover:border-white/40"
    >
      {copied ? "복사 완료" : label}
    </button>
  );
}

