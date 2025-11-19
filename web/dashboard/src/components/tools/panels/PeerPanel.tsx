"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import dynamic from "next/dynamic";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import clsx from "clsx";

import SpotlightCard from "@/components/ui/SpotlightCard";
import type { CommanderRouteDecision } from "@/lib/chatApi";
import { useToolStore } from "@/store/toolStore";
import type { ValueChainData } from "./ValueChainGraph";
const ValueChainGraph = dynamic(() => import("./ValueChainGraph").then((module) => module.ValueChainGraph), {
  ssr: false,
});

type PeerPanelProps = {
  params?: Record<string, unknown>;
  decision?: CommanderRouteDecision | null;
};

type PeerSeries = {
  ticker: string;
  label?: string | null;
  data: { date: string; value: number }[];
  isAverage?: boolean;
};

type PeerCompareResponse = {
  ticker: string;
  label?: string | null;
  periodDays: number;
  peers: { ticker: string; label?: string | null }[];
  series: PeerSeries[];
  latest: { ticker: string; label?: string | null; value: number | null }[];
  interpretation: string;
  correlations: { ticker: string; label?: string | null; value: number | null }[];
  llm_summary?: string | null;
  valueChain?: ValueChainData | null;
  valueChainSummary?: string | null;
};

const COLOR_PALETTE = ["#60A5FA", "#F472B6", "#34D399", "#FBBF24", "#A78BFA", "#2DD4BF"];

const tooltipFormatter = (value: number, name: string) => [`${value.toFixed(2)}%`, name];

const buildChartDataset = (series: PeerSeries[]) => {
  const map: Record<string, Record<string, number | string>> = {};
  series.forEach((entry) => {
    entry.data.forEach((point) => {
      const row = (map[point.date] ||= { date: point.date });
      row[entry.ticker] = point.value;
    });
  });
  return Object.values(map).sort((a, b) => String(a.date).localeCompare(String(b.date)));
};

const toPercent = (value: number | null | undefined) =>
  typeof value === "number" ? `${value >= 0 ? "+" : ""}${value.toFixed(2)}%` : "-";

export function PeerPanel({ params, decision }: PeerPanelProps) {
  const fallbackTicker =
    (typeof decision?.tickers?.[0] === "string" && decision.tickers[0]) ||
    (typeof params?.ticker === "string" && params.ticker) ||
    "005930";
  const ticker = fallbackTicker;
  const period = typeof params?.period_days === "number" ? params.period_days : 30;

  const [data, setData] = useState<PeerCompareResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"performance" | "network">("performance");
  const sessionId = useToolStore((state) => state.entry?.sessionId ?? null);
  const registerToolContext = useToolStore((state) => state.registerToolContext);
  const publishToolSnapshot = useToolStore((state) => state.publishToolSnapshot);
  const openTool = useToolStore((state) => state.openTool);

  useEffect(() => {
    let mounted = true;
    const controller = new AbortController();
    setLoading(true);
    setError(null);

    const fetchPeerData = async () => {
      try {
        const response = await fetch("/api/v1/tools/peer-compare", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ticker, period_days: period }),
          signal: controller.signal,
        });
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }
        const payload = (await response.json()) as PeerCompareResponse & { llm_summary?: string };
        if (!mounted) return;
        setData(payload);
        if (payload.llm_summary) {
          registerToolContext(sessionId, payload.llm_summary);
        }
        if (payload.valueChain) {
          publishToolSnapshot({
            sessionId,
            summary: `${payload.label ?? ticker} 밸류체인 업데이트`,
            attachments: [
              {
                type: "value_chain",
                title: `${payload.label ?? ticker} Value Chain`,
                data: payload.valueChain as Record<string, unknown>,
              },
            ],
          });
        }
      } catch (fetchError) {
        if (!mounted) return;
        setError(fetchError instanceof Error ? fetchError.message : "Peer 데이터를 불러오지 못했습니다.");
        setData(null);
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    };

    void fetchPeerData();

    return () => {
      mounted = false;
      controller.abort();
    };
  }, [ticker, period, registerToolContext, sessionId, publishToolSnapshot]);

  const chartDataset = useMemo(() => {
    if (!data?.series?.length) {
      return [];
    }
    return buildChartDataset(data.series);
  }, [data]);

  const summaryCards = data?.latest ?? [];
  const correlations = data?.correlations ?? [];

  const handleNodeSelect = useCallback(
    (nextTicker: string) => {
      if (!nextTicker || !nextTicker.trim()) {
        return;
      }
      if (data?.ticker && nextTicker.replace(/\s+/g, "") === data.ticker) {
        return;
      }
      openTool("peer_compare", { ticker: nextTicker });
    },
    [data?.ticker, openTool],
  );

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center rounded-3xl border border-white/10 bg-white/5 text-sm text-slate-200">
        Peer 데이터를 불러오는 중입니다...
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-full items-center justify-center rounded-3xl border border-rose-500/40 bg-rose-500/5 px-6 text-sm text-rose-100">
        {error}
      </div>
    );
  }

  if (!data) {
    return (
      <div className="flex h-full items-center justify-center rounded-3xl border border-white/10 bg-white/5 text-sm text-slate-300">
        비교 데이터를 찾지 못했습니다. 다른 종목으로 시도해 주세요.
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col gap-4 overflow-hidden">
      <div className="flex flex-wrap gap-2 rounded-full bg-slate-900/40 p-1 text-xs text-slate-400">
        <button
          type="button"
          onClick={() => setActiveTab("performance")}
          className={clsx(
            "rounded-full px-4 py-1 transition",
            activeTab === "performance" ? "bg-white/10 text-white" : "hover:text-white",
          )}
        >
          퍼포먼스
        </button>
        <button
          type="button"
          onClick={() => setActiveTab("network")}
          className={clsx(
            "rounded-full px-4 py-1 transition",
            activeTab === "network" ? "bg-white/10 text-white" : "hover:text-white",
          )}
        >
          밸류체인
        </button>
      </div>

      {activeTab === "performance" ? (
        <>
          <div className="grid gap-4 md:grid-cols-3">
            {summaryCards.map((item) => (
              <SpotlightCard key={item.ticker} className="bg-white/[0.02] p-4">
                <p className="text-xs uppercase tracking-[0.4em] text-indigo-200">{item.label ?? item.ticker}</p>
                <p className="mt-3 text-2xl font-semibold text-white">{toPercent(item.value)}</p>
                <p className="mt-1 text-xs text-slate-400">기준 대비 {data.periodDays}일 상대 수익률</p>
              </SpotlightCard>
            ))}
          </div>

          <SpotlightCard className="flex-1 bg-white/[0.02] p-6">
            <div className="mb-4 flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
              <div>
                <p className="text-xs uppercase tracking-[0.4em] text-indigo-200">Relative Performance</p>
                <h3 className="text-lg font-semibold text-white">{data.label ?? data.ticker}</h3>
                <p className="text-xs text-slate-400">{data.periodDays} 거래일 동안의 상대 수익률 비교</p>
              </div>
              <p className="text-sm text-slate-300">{data.interpretation}</p>
            </div>
            {chartDataset.length === 0 ? (
              <div className="flex h-64 items-center justify-center text-sm text-slate-400">
                표시할 차트 데이터가 없습니다.
              </div>
            ) : (
              <div className="h-72 w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartDataset} margin={{ top: 10, right: 24, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="4 4" stroke="#1E293B" />
                    <XAxis dataKey="date" stroke="#94A3B8" tick={{ fontSize: 12 }} minTickGap={20} />
                    <YAxis stroke="#94A3B8" tickFormatter={(value) => `${value.toFixed(1)}%`} />
                    <Tooltip formatter={tooltipFormatter} />
                    {data.series.map((series, index) => (
                      <Line
                        key={series.ticker}
                        type="monotone"
                        dataKey={series.ticker}
                        name={series.label ?? series.ticker}
                        stroke={series.isAverage ? "#FACC15" : COLOR_PALETTE[index % COLOR_PALETTE.length]}
                        strokeDasharray={series.isAverage ? "5 4" : undefined}
                        strokeWidth={series.isAverage ? 2 : 3}
                        dot={false}
                        activeDot={{ r: 4 }}
                      />
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}
          </SpotlightCard>

          <SpotlightCard className="bg-white/[0.02] p-5">
            <p className="text-xs uppercase tracking-[0.4em] text-indigo-200">Correlation</p>
            {correlations.length === 0 ? (
              <p className="mt-3 text-sm text-slate-400">상관관계를 계산할 데이터가 부족합니다.</p>
            ) : (
              <div className="mt-4 overflow-x-auto">
                <table className="w-full text-left text-sm text-slate-200">
                  <thead className="text-xs uppercase tracking-wide text-slate-400">
                    <tr>
                      <th className="pb-2">Peer</th>
                      <th className="pb-2 text-right">30일 상관계수</th>
                    </tr>
                  </thead>
                  <tbody>
                    {correlations.map((row) => (
                      <tr key={row.ticker} className="border-t border-white/5">
                        <td className="py-2">{row.label ?? row.ticker}</td>
                        <td className={clsx("py-2 text-right", typeof row.value === "number" && row.value < 0.5 ? "text-amber-300" : "text-emerald-200")}>
                          {typeof row.value === "number" ? row.value.toFixed(2) : "N/A"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </SpotlightCard>
        </>
      ) : (
        <div className="flex flex-col gap-4">
          <SpotlightCard className="bg-white/[0.02] p-5">
            <p className="text-xs uppercase tracking-[0.4em] text-indigo-200">Value Chain Network</p>
            {data.valueChain ? (
              <div className="mt-4">
                <ValueChainGraph data={data.valueChain} onNodeSelect={handleNodeSelect} />
                <p className="mt-4 text-sm text-slate-300">
                  {data.valueChainSummary || "밸류체인 관계 요약을 준비 중입니다."}
                </p>
              </div>
            ) : (
              <p className="mt-3 text-sm text-slate-400">밸류체인을 구성할 수 있는 데이터가 부족합니다.</p>
            )}
          </SpotlightCard>
        </div>
      )}
    </div>
  );
}
