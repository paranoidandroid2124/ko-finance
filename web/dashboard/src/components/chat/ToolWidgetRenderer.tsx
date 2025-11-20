"use client";

import dynamic from "next/dynamic";
import { useMemo } from "react";

import type { ToolAttachment } from "@/store/chatStore";
import { useToolStore } from "@/store/toolStore";
import type { ValueChainData } from "@/components/tools/panels/ValueChainGraph";
import NewsCardsWidget from "@/components/chat/widgets/NewsCardsWidget";
import { StockLineChart } from "@/components/chat/widgets/StockLineChart";
import { FinancialTable } from "@/components/chat/widgets/FinancialTable";
import { StatCard } from "@/components/chat/widgets/StatCard";

const ValueChainGraph = dynamic(() => import("@/components/tools/panels/ValueChainGraph").then((module) => module.ValueChainGraph), {
  ssr: false,
});

type ToolWidgetRendererProps = {
  attachment: ToolAttachment;
};

export default function ToolWidgetRenderer({ attachment }: ToolWidgetRendererProps) {
  const openTool = useToolStore((state) => state.openTool);

  const handleDrillDown = (ticker: string) => {
    if (!ticker || !ticker.trim()) {
      return;
    }
    openTool("peer_compare", { ticker: ticker.trim() });
  };

  const content = useMemo(() => {
    switch (attachment.type) {
      case "news_cards": {
        const items = Array.isArray(attachment.data?.items) ? (attachment.data?.items as unknown[]) : [];
        return (
          <NewsCardsWidget
            title={attachment.title}
            description={attachment.description}
            items={items as Record<string, unknown>[]}
          />
        );
      }
      case "value_chain": {
        return (
          <div>
            {attachment.title ? <p className="mb-2 text-xs font-semibold uppercase text-indigo-200">{attachment.title}</p> : null}
            <ValueChainGraph
              data={attachment.data as ValueChainData | undefined}
              onNodeSelect={(ticker) => handleDrillDown(ticker)}
            />
            {attachment.description ? <p className="mt-2 text-xs text-slate-400">{attachment.description}</p> : null}
          </div>
        );
      }
      case "line": {
        return (
          <StockLineChart
            title={attachment.title ?? attachment.label}
            description={attachment.description}
            label={attachment.label}
            unit={attachment.unit ?? undefined}
            data={attachment.data}
          />
        );
      }
      case "financials": {
        return (
          <FinancialTable
            title={attachment.title}
            description={attachment.description}
            headers={attachment.headers}
            rows={attachment.rows}
          />
        );
      }
      case "summary": {
        return <StatCard title={attachment.title} value={attachment.value} description={attachment.description} />;
      }
      default:
        return (
          <pre className="overflow-x-auto rounded-xl bg-black/60 p-3 text-[11px] text-slate-200">
            {JSON.stringify(attachment.data ?? {}, null, 2)}
          </pre>
        );
    }
  }, [attachment, openTool]);

  return <div className="rounded-2xl border border-white/10 bg-white/5 p-3">{content}</div>;
}
