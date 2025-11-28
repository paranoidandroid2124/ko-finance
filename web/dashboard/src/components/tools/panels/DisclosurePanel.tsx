"use client";

import type { CommanderRouteDecision } from "@/lib/chatApi";
import { useCallback, useEffect, useMemo, useState } from "react";

import { GenericToolPlaceholder } from "./GenericToolPlaceholder";

type DisclosurePanelProps = {
  params?: Record<string, unknown>;
  decision?: CommanderRouteDecision | null;
};

type Highlight = {
  section?: string | null;
  text?: string | null;
  page?: number | null;
  score?: number | null;
};

type DisclosurePayload = {
  filing_id: string;
  receipt_no?: string | null;
  title?: string | null;
  company?: string | null;
  highlights: Highlight[];
  pdfViewerUrl?: string | null;
};

export function DisclosurePanel({ params, decision }: DisclosurePanelProps) {
  const filingId =
    (typeof params?.filing_id === "string" && params.filing_id.trim()) ||
    (typeof decision?.metadata?.filing_id === "string" && decision.metadata.filing_id.trim()) ||
    undefined;
  const receiptNo =
    (typeof params?.receipt_no === "string" && params.receipt_no.trim()) ||
    (typeof decision?.metadata?.receipt_no === "string" && decision.metadata.receipt_no.trim()) ||
    undefined;
  const ticker = typeof params?.ticker === "string" ? params.ticker : undefined;
  const query = typeof params?.query === "string" ? params.query : undefined;

  const [data, setData] = useState<DisclosurePayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const buildViewerLink = useCallback(
    (base: string | null | undefined, highlight?: Highlight) => {
      if (!base) return null;
      const url = new URL(base, typeof window !== "undefined" ? window.location.origin : undefined);
      const page = highlight?.page;
      const text = highlight?.text;
      if (page && page > 0) {
        url.hash = `page=${page}`;
      }
      if (text && text.trim()) {
        const searchParam = encodeURIComponent(text.slice(0, 120));
        url.hash = url.hash ? `${url.hash}&search=${searchParam}` : `search=${searchParam}`;
      }
      return url.toString();
    },
    [],
  );

  useEffect(() => {
    if (!filingId && !receiptNo) {
      setData(null);
      return;
    }
    let mounted = true;
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    const run = async () => {
      try {
        const params = new URLSearchParams();
        if (filingId) params.set("filing_id", filingId);
        if (receiptNo) params.set("receipt_no", receiptNo);
        if (query) params.set("highlight_query", query);
        const res = await fetch(`/api/v1/tools/disclosure-viewer?${params.toString()}`, { signal: controller.signal });
        if (!res.ok) {
          throw new Error(`failed ${res.status}`);
        }
        const payload = (await res.json()) as DisclosurePayload;
        if (!mounted) return;
        setData(payload);
      } catch (err) {
        if (!mounted) return;
        setError(err instanceof Error ? err.message : "공시를 불러오지 못했습니다.");
        setData(null);
      } finally {
        if (mounted) setLoading(false);
      }
    };
    void run();
    return () => {
      mounted = false;
      controller.abort();
    };
  }, [filingId, query, receiptNo]);

  if (!filingId && !receiptNo) {
    return (
      <GenericToolPlaceholder
        title="지능형 공시 뷰어"
        description="공시 원문에서 중요 문단을 찾아 하이라이트로 점프합니다."
        hint="필링 ID나 접수번호가 필요합니다. Commander가 공시를 열면 여기 표시됩니다."
      />
    );
  }

  if (loading) {
    return (
      <GenericToolPlaceholder
        title="지능형 공시 뷰어"
        description="공시 원문에서 중요 문단을 찾아 하이라이트로 점프합니다."
        hint="불러오는 중..."
      />
    );
  }

    if (error || !data) {
      return (
        <GenericToolPlaceholder
          title="지능형 공시 뷰어"
          description="공시 원문에서 중요 문단을 찾아 하이라이트로 점프합니다."
        hint={error ?? "공시를 찾지 못했습니다."}
      />
    );
  }

  return (
    <GenericToolPlaceholder
      title="지능형 공시 뷰어"
      description="공시 원문에서 중요 문단을 찾아 하이라이트로 점프합니다."
      hint={`${data.company ?? ticker ?? ""} - ${data.title ?? ""}`}
    >
      <div className="space-y-3 text-sm">
        {data.highlights?.length ? (
          <div className="space-y-2 rounded-2xl border border-border-subtle bg-background-cardDark/60 p-3">
            <p className="text-xs font-semibold uppercase tracking-wide text-text-secondary">하이라이트</p>
            <div className="space-y-2">
              {data.highlights.map((h, idx) => {
                const link = buildViewerLink(data.pdfViewerUrl, h);
                return (
                  <div key={`${h.section}-${idx}`} className="rounded-xl border border-border-subtle/60 bg-background-cardDark/60 p-2">
                    <div className="flex items-center justify-between gap-2 text-[11px] text-text-tertiary">
                      <div className="flex items-center gap-2">
                        {h.section ? <span className="font-semibold text-text-secondary">{h.section}</span> : null}
                        {typeof h.page === "number" ? <span className="text-text-secondary">p.{h.page}</span> : null}
                        {typeof h.score === "number" ? <span className="text-text-secondary">score {h.score.toFixed(2)}</span> : null}
                      </div>
                      {link ? (
                        <a
                          href={link}
                          target="_blank"
                          rel="noreferrer"
                          className="rounded-full border border-primary/40 px-2 py-0.5 text-[10px] font-semibold text-primary hover:border-primary hover:text-primary"
                        >
                          뷰어에서 보기
                        </a>
                      ) : null}
                    </div>
                    {h.text ? <p className="mt-1 text-text-primary">{h.text}</p> : null}
                  </div>
                );
              })}
            </div>
          </div>
        ) : (
          <p className="text-sm text-text-secondary">하이라이트를 찾지 못했습니다.</p>
        )}
        {data.pdfViewerUrl ? (
          <a
            href={buildViewerLink(data.pdfViewerUrl, data.highlights?.[0]) ?? data.pdfViewerUrl}
            target="_blank"
            rel="noreferrer"
            className="inline-flex w-fit items-center gap-2 rounded-full border border-primary/60 px-3 py-1 text-xs font-semibold text-primary hover:border-primary hover:text-primary"
          >
            PDF 뷰어 열기
          </a>
        ) : null}
        {ticker ? <p className="text-xs text-text-secondary">요청된 종목: {ticker}</p> : null}
        {decision?.reason ? <p className="text-xs text-text-secondaryLight">{decision.reason}</p> : null}
      </div>
    </GenericToolPlaceholder>
  );
}
