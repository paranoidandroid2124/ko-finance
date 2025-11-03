"use client";

import { useEffect, useRef, useState } from "react";

import clsx from "classnames";

import {
  AdminButtonSpinner,
  AdminSuccessIcon,
  formatJsonValue,
  parseJsonRecord,
} from "@/components/admin/adminFormUtils";
import { useNewsPipeline, useUpdateNewsPipeline } from "@/hooks/useAdminConfig";
import type { ToastInput } from "@/store/toastStore";

interface AdminNewsPipelinePanelProps {
  adminActor?: string | null;
  toast: (toast: ToastInput) => string;
}

export function AdminNewsPipelinePanel({ adminActor, toast }: AdminNewsPipelinePanelProps) {
  const { data: newsPipelineData, isLoading: isNewsLoading, refetch: refetchNewsPipeline } = useNewsPipeline(true);
  const updateNews = useUpdateNewsPipeline();

  const [newsDraft, setNewsDraft] = useState({
    rssText: "",
    sectorMappingsJson: "{}",
    sentimentJson: "{}",
    actor: "",
    note: "",
    error: undefined as string | undefined,
  });
  const [newsSaveSuccess, setNewsSaveSuccess] = useState(false);
  const newsSuccessTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!newsPipelineData?.pipeline) {
      return;
    }
    setNewsDraft((prev) => ({
      ...prev,
      rssText: (newsPipelineData.pipeline.rssFeeds ?? []).join("\n"),
      sectorMappingsJson: formatJsonValue(newsPipelineData.pipeline.sectorMappings, "{\n  \"금융\": [\"은행\"]\n}"),
      sentimentJson: formatJsonValue(newsPipelineData.pipeline.sentiment, "{\n  \"threshold\": 0.55\n}"),
      actor: adminActor ?? prev.actor,
      note: "",
      error: undefined,
    }));
  }, [newsPipelineData, adminActor]);

  useEffect(() => {
    return () => {
      if (newsSuccessTimer.current) {
        clearTimeout(newsSuccessTimer.current);
      }
    };
  }, []);

  const handleNewsSubmit = async () => {
    if (newsSuccessTimer.current) {
      clearTimeout(newsSuccessTimer.current);
      newsSuccessTimer.current = null;
    }
    setNewsSaveSuccess(false);

    let sectorMappings: Record<string, string[]>;
    let sentiment: Record<string, unknown>;
    try {
      const parsed = parseJsonRecord(newsDraft.sectorMappingsJson, "섹터 매핑");
      sectorMappings = Object.entries(parsed).reduce<Record<string, string[]>>((acc, [key, value]) => {
        if (Array.isArray(value)) {
          acc[key] = value.map((item) => String(item));
        } else if (typeof value === "string") {
          acc[key] = [value];
        } else {
          acc[key] = [];
        }
        return acc;
      }, {});
    } catch (error) {
      const message = error instanceof Error ? error.message : "섹터 매핑 JSON을 확인해 주세요.";
      setNewsDraft((prev) => ({ ...prev, error: message }));
      return;
    }

    try {
      sentiment = parseJsonRecord(newsDraft.sentimentJson, "감성 설정");
    } catch (error) {
      const message = error instanceof Error ? error.message : "감성 설정 JSON을 확인해 주세요.";
      setNewsDraft((prev) => ({ ...prev, error: message }));
      return;
    }

    const rssFeeds = newsDraft.rssText
      .split("\n")
      .map((item) => item.trim())
      .filter(Boolean);

    try {
      await updateNews.mutateAsync({
        rssFeeds,
        sectorMappings,
        sentiment,
        actor: newsDraft.actor.trim() || adminActor || "unknown-admin",
        note: newsDraft.note.trim() || null,
      });
      toast({
        id: "admin/ops/news/success",
        title: "뉴스 파이프라인이 저장됐어요",
        message: "RSS 및 섹터 설정이 최신 상태예요.",
        intent: "success",
      });
      setNewsSaveSuccess(true);
      newsSuccessTimer.current = setTimeout(() => setNewsSaveSuccess(false), 1800);
      setNewsDraft((prev) => ({ ...prev, error: undefined, note: "" }));
      await refetchNewsPipeline();
    } catch (error) {
      const message = error instanceof Error ? error.message : "저장 중 문제가 발생했어요.";
      toast({
        id: "admin/ops/news/error",
        title: "뉴스 파이프라인 저장 실패",
        message,
        intent: "error",
      });
      setNewsSaveSuccess(false);
    }
  };

  return (
    <section className="space-y-4 rounded-xl border border-border-light bg-background-base p-4 dark:border-border-dark dark:bg-background-cardDark">
      <h3 className="text-sm font-semibold uppercase tracking-wide text-text-secondaryLight dark:text-text-secondaryDark">
        뉴스 파이프라인
      </h3>
      <label className="flex flex-col gap-2 text-sm">
        <span className="font-semibold text-text-primaryLight dark:text-text-primaryDark">RSS 피드 (줄바꿈 구분)</span>
        <textarea
          value={newsDraft.rssText}
          onChange={(event) => setNewsDraft((prev) => ({ ...prev, rssText: event.target.value }))}
          className="min-h-[140px] rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
          placeholder="https://www.hankyung.com/feed"
        />
      </label>
      <label className="flex flex-col gap-2 text-sm">
        <span className="font-semibold text-text-primaryLight dark:text-text-primaryDark">섹터 매핑 (JSON)</span>
        <textarea
          value={newsDraft.sectorMappingsJson}
          onChange={(event) => setNewsDraft((prev) => ({ ...prev, sectorMappingsJson: event.target.value }))}
          className="min-h-[160px] rounded-lg border border-border-light bg-background-base px-3 py-2 font-mono text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
        />
      </label>
      <label className="flex flex-col gap-2 text-sm">
        <span className="font-semibold text-text-primaryLight dark:text-text-primaryDark">감성 분석 설정 (JSON)</span>
        <textarea
          value={newsDraft.sentimentJson}
          onChange={(event) => setNewsDraft((prev) => ({ ...prev, sentimentJson: event.target.value }))}
          className="min-h-[120px] rounded-lg border border-border-light bg-background-base px-3 py-2 font-mono text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
        />
      </label>
      <div className="grid gap-3 md:grid-cols-2">
        <label className="flex flex-col gap-1 text-sm text-text-secondaryLight dark:text-text-secondaryDark">
          실행자(Actor)
          <input
            type="text"
            value={newsDraft.actor}
            onChange={(event) => setNewsDraft((prev) => ({ ...prev, actor: event.target.value }))}
            placeholder={adminActor ?? "운영자 이름"}
            className="rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
          />
        </label>
        <label className="flex flex-col gap-1 text-sm text-text-secondaryLight dark:text-text-secondaryDark">
          변경 메모
          <input
            type="text"
            value={newsDraft.note}
            onChange={(event) => setNewsDraft((prev) => ({ ...prev, note: event.target.value }))}
            placeholder="예: 신규 RSS 추가"
            className="rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
          />
        </label>
      </div>
      {newsDraft.error ? (
        <p className="rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-sm text-amber-700 dark:border-amber-500/70 dark:bg-amber-500/10 dark:text-amber-200">
          {newsDraft.error}
        </p>
      ) : null}
      <div className="flex flex-wrap items-center justify-end gap-3">
        <button
          type="button"
          onClick={() => refetchNewsPipeline()}
          className="inline-flex items-center gap-2 rounded-lg border border-border-light px-4 py-2 text-sm font-semibold text-text-secondaryLight transition duration-150 hover:bg-border-light/30 active:translate-y-[1px] active:scale-[0.98] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-border-light dark:border-border-dark dark:text-text-secondaryDark dark:hover:bg-border-dark/40 dark:focus-visible:outline-border-dark"
          disabled={isNewsLoading}
        >
          최신 상태 불러오기
        </button>
        <button
          type="button"
          onClick={handleNewsSubmit}
          disabled={updateNews.isPending}
          className={clsx(
            "inline-flex items-center gap-2 rounded-lg bg-primary px-5 py-2 text-sm font-semibold text-white transition duration-150 active:translate-y-[1px] active:scale-[0.98] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary",
            updateNews.isPending && "cursor-not-allowed opacity-60",
          )}
        >
          {updateNews.isPending ? (
            <>
              <AdminButtonSpinner className="border-white/40 border-t-white" />
              <span>저장 중…</span>
            </>
          ) : newsSaveSuccess ? (
            <>
              <AdminSuccessIcon className="text-white" />
              <span>저장 완료!</span>
            </>
          ) : (
            "파이프라인 저장"
          )}
        </button>
      </div>
    </section>
  );
}
