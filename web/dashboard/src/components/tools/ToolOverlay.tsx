"use client";

import { useMemo } from "react";
import { useToolStore } from "@/store/toolStore";
import { EventStudyPanel } from "./panels/EventStudyPanel";

const TOOL_TITLES: Record<string, string> = {
  TOOL_EVENT_STUDY: "📊 이벤트 스터디",
  TOOL_DISCLOSURE: "📑 공시 뷰어",
  TOOL_NEWS: "📰 뉴스 브리핑",
};

export function ToolOverlay() {
  const { isOpen, activeTool, params, closeTool } = useToolStore();

  const heading = useMemo(() => {
    if (!activeTool) {
      return "도구 미지정";
    }
    const baseTitle = TOOL_TITLES[activeTool] ?? activeTool;
    const tickerLabel = typeof params?.ticker === "string" ? ` · ${params.ticker}` : "";
    return `${baseTitle}${tickerLabel}`;
  }, [activeTool, params?.ticker]);

  const renderContent = () => {
    if (!activeTool) {
      return (
        <div className="flex h-full items-center justify-center rounded-2xl border border-dashed border-gray-300 bg-gray-50 text-sm text-gray-500 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-400">
          도구를 실행하면 이 영역에 분석 패널이 표시됩니다.
        </div>
      );
    }
    switch (activeTool) {
      case "TOOL_EVENT_STUDY":
        return <EventStudyPanel params={params} />;
      case "TOOL_DISCLOSURE":
      case "TOOL_NEWS":
        return (
          <div className="flex h-full flex-col items-center justify-center rounded-2xl border border-dashed border-gray-300 bg-gray-50 text-center text-sm text-gray-500 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-400">
            <p className="mb-2 font-medium">준비 중인 기능입니다</p>
            <p className="text-xs text-gray-400">
              {activeTool} 패널은 차후 단계에서 연결될 예정입니다.
            </p>
          </div>
        );
      default:
        return (
          <div className="flex h-full flex-col items-center justify-center rounded-2xl border border-dashed border-gray-300 bg-gray-50 text-sm text-gray-500 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-400">
            <p>인식되지 않은 도구: {activeTool}</p>
          </div>
        );
    }
  };

  if (!isOpen) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/50 backdrop-blur-sm">
      <div className="flex h-full w-full max-w-[820px] flex-col bg-white p-6 text-gray-900 shadow-2xl transition-transform dark:bg-background-dark dark:text-text-primaryDark">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-xl font-semibold">{heading}</h2>
          <button
            onClick={closeTool}
            className="rounded-md border border-gray-200 px-3 py-1 text-sm text-gray-600 hover:bg-gray-100 dark:border-gray-700 dark:text-gray-300 dark:hover:bg-gray-800"
          >
            닫기 ✖️
          </button>
        </div>
        <div className="mb-4 text-sm text-gray-500 dark:text-gray-400">
          채팅 라우터가 감지한 의도에 따라 실시간으로 분석 툴을 불러옵니다. 데이터는 순차적으로 연결될 예정입니다.
        </div>
        <div className="flex-1 overflow-hidden">{renderContent()}</div>
      </div>
    </div>
  );
}
