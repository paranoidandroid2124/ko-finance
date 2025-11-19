"use client";

import { useMemo } from "react";

import { useToolStore } from "@/store/toolStore";
import { usePlanStore } from "@/store/planStore";
import { COMMANDER_TOOL_REGISTRY } from "@/components/tools/registry";

const PAYWALL_LABELS: Record<string, string> = {
  free: "Free",
  starter: "Starter",
  pro: "Pro",
  enterprise: "Enterprise",
};

export function ToolOverlay() {
  const isOpen = useToolStore((state) => state.isOpen);
  const entry = useToolStore((state) => state.entry);
  const closeTool = useToolStore((state) => state.closeTool);
  const submitMemoryDraft = useToolStore((state) => state.submitMemoryDraft);
  const toolDefinition = entry ? COMMANDER_TOOL_REGISTRY[entry.toolId] : null;
  const memoryFlags = usePlanStore((state) => state.memoryFlags);

  const heading = useMemo(() => {
    if (!toolDefinition) {
      return "도구 미지정";
    }
    const tickerLabel = typeof entry?.params?.ticker === "string" ? ` · ${entry?.params?.ticker}` : "";
    return `${toolDefinition.title}${tickerLabel}`;
  }, [entry?.params?.ticker, toolDefinition]);

  if (!isOpen || !entry || !toolDefinition) {
    return null;
  }

  const Panel = toolDefinition.component;
  const paywallLabel = PAYWALL_LABELS[entry.paywall] ?? entry.paywall;
  const requiresLightMem = Boolean(
    entry.decision?.requires_context?.some((ctx) => typeof ctx === "string" && ctx.toLowerCase() === "lightmem.summary"),
  );
  const lightMemAllowed = Boolean(memoryFlags.chat);

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/50 backdrop-blur-sm">
      <div className="flex h-full w-full max-w-[880px] flex-col gap-4 bg-white p-6 text-gray-900 shadow-2xl transition-transform dark:bg-background-dark dark:text-text-primaryDark">
        <div className="flex flex-col gap-4 border-b border-border-light pb-4 dark:border-border-dark">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-primary dark:text-primary.dark">
                Commander Tool
              </p>
              <h2 className="text-2xl font-semibold">{heading}</h2>
              <p className="text-sm text-text-secondaryLight dark:text-text-secondaryDark">{toolDefinition.subtitle}</p>
            </div>
            <div className="flex items-center gap-2">
              <span className="rounded-full border border-border-light px-3 py-1 text-xs font-semibold text-text-secondaryLight dark:border-border-dark dark:text-text-secondaryDark">
                {toolDefinition.uiContainer === "overlay"
                  ? "Overlay"
                  : toolDefinition.uiContainer === "side_panel"
                    ? "Side Panel"
                    : "Inline"}
              </span>
              <span className="rounded-full border border-primary/30 px-3 py-1 text-xs font-semibold text-primary dark:border-primary.dark/50 dark:text-primary.dark">
                {paywallLabel}
              </span>
              <button
                onClick={() => {
                  void submitMemoryDraft().finally(() => closeTool());
                }}
                className="rounded-md border border-gray-200 px-3 py-1 text-sm text-gray-600 hover:bg-gray-100 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-800"
              >
                닫기 ✕
              </button>
            </div>
          </div>
          {entry.requiresContext.length ? (
            <div className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
              <p className="mb-1 font-semibold text-text-primaryLight dark:text-text-primaryDark">필요 컨텍스트</p>
              <p>{entry.requiresContext.join(", ")}</p>
            </div>
          ) : null}
          {entry.decision?.reason ? (
            <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">{entry.decision.reason}</p>
          ) : null}
        </div>
        {!lightMemAllowed && requiresLightMem ? (
          <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-xs text-amber-800 dark:border-amber-400/40 dark:bg-amber-500/10 dark:text-amber-200">
            이 도구는 챗 메모리를 요구하지만 현재 플랜/설정에서 LightMem이 비활성화되어 있어 자동 비교 기능이 제한됩니다.
          </div>
        ) : null}
        <div className="flex-1 overflow-hidden">
          <Panel params={entry.params} decision={entry.decision ?? null} />
        </div>
      </div>
    </div>
  );
}
