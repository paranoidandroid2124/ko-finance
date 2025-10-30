"use client";

import clsx from "classnames";
import { useMemo, useState } from "react";

import { useTossWebhookAudit } from "@/hooks/useAdminQuickActions";
import { requestTossWebhookReplay } from "@/lib/adminApi";
import { useToastStore } from "@/store/toastStore";

const RESULT_TONE: Record<string, string> = {
  processed: "bg-emerald-100 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300",
  duplicate: "bg-slate-200 text-slate-700 dark:bg-slate-500/20 dark:text-slate-200",
  upgrade_applied: "bg-primary/10 text-primary dark:bg-primary/20",
  checkout_cleared: "bg-amber-100 text-amber-700 dark:bg-amber-500/10 dark:text-amber-300",
  status_ignored: "bg-slate-200 text-slate-700 dark:bg-slate-500/20 dark:text-slate-200",
  default: "bg-slate-200 text-slate-700 dark:bg-slate-500/20 dark:text-slate-200",
};

const formatDateTime = (iso?: string | null) => {
  if (!iso) {
    return "기록 없음";
  }
  const parsed = new Date(iso);
  if (Number.isNaN(parsed.getTime())) {
    return iso;
  }
  return parsed.toLocaleString();
};

export function TossWebhookAuditPanel() {
  const [limit, setLimit] = useState(25);
  const { data, isLoading, refetch, isFetching } = useTossWebhookAudit(limit);
  const pushToast = useToastStore((state) => state.show);

  const entries = useMemo(() => data ?? [], [data]);

  const handleReplay = async (transmissionId?: string | null) => {
    if (!transmissionId) {
      pushToast({
        id: `admin/webhook/replay/${Date.now()}`,
        title: "재시도할 수 없어요",
        message: "transmissionId가 없는 이벤트입니다.",
        intent: "error",
      });
      return;
    }
    try {
      await requestTossWebhookReplay(transmissionId);
      pushToast({
        id: `admin/webhook/replay/success/${transmissionId}`,
        title: "웹훅 재시도 요청 완료",
        message: "토스 웹훅 재시도가 요청되었어요.",
        intent: "success",
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : "웹훅 재시도 중 오류가 발생했어요.";
      pushToast({
        id: `admin/webhook/replay/error/${Date.now()}`,
        title: "재시도 요청 실패",
        message,
        intent: "error",
      });
    }
  };

  return (
    <section className="rounded-2xl border border-border-light bg-background-cardLight p-6 shadow-card dark:border-border-dark dark:bg-background-cardDark">
      <div className="flex flex-col gap-3 border-b border-border-light pb-4 dark:border-border-dark lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h2 className="text-lg font-semibold text-text-primaryLight dark:text-text-primaryDark">Toss 웹훅 감사 로그</h2>
          <p className="text-sm text-text-secondaryLight dark:text-text-secondaryDark">
            최근 수신된 웹훅 이벤트와 처리 상태를 확인하고, 문제가 있을 경우 재시도를 준비하세요.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
            표시 개수
            <select
              value={limit}
              onChange={(event) => setLimit(Number.parseInt(event.target.value, 10))}
              className="rounded-lg border border-border-light bg-background-base px-2 py-1 text-xs focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark"
            >
              <option value={10}>10</option>
              <option value={25}>25</option>
              <option value={50}>50</option>
              <option value={100}>100</option>
            </select>
          </label>
          <button
            type="button"
            onClick={() => refetch()}
            disabled={isFetching}
            className={clsx(
              "inline-flex items-center rounded-lg border border-border-light px-3 py-1.5 text-xs font-semibold text-text-secondaryLight transition hover:bg-border-light/30 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-border-light dark:border-border-dark dark:text-text-secondaryDark dark:hover:bg-border-dark/40 dark:focus-visible:outline-border-dark",
              isFetching ? "cursor-not-allowed opacity-60" : "",
            )}
          >
            {isFetching ? "새로고침…" : "새로고침"}
          </button>
        </div>
      </div>

      <div className="mt-4 overflow-x-auto">
        <table className="min-w-full table-fixed text-sm">
          <thead>
            <tr className="text-left text-xs uppercase text-text-tertiaryLight dark:text-text-tertiaryDark">
              <th className="w-40 px-3 py-2">수신 시각</th>
              <th className="w-28 px-3 py-2">결과</th>
              <th className="w-40 px-3 py-2">주문 / 전송 ID</th>
              <th className="w-32 px-3 py-2">상태</th>
              <th className="px-3 py-2">메시지</th>
              <th className="w-24 px-3 py-2 text-right">작업</th>
            </tr>
          </thead>
          <tbody>
            {isLoading ? (
              <tr>
                <td colSpan={6} className="px-3 py-6 text-center text-sm text-text-secondaryLight dark:text-text-secondaryDark">
                  웹훅 감사 로그를 불러오는 중이에요…
                </td>
              </tr>
            ) : entries.length === 0 ? (
              <tr>
                <td colSpan={6} className="px-3 py-6 text-center text-sm text-text-secondaryLight dark:text-text-secondaryDark">
                  최근 감사 로그가 없습니다.
                </td>
              </tr>
            ) : (
              entries.map((entry, index) => {
                const context = entry.context ?? {};
                const orderId = (context["order_id"] ?? context["orderId"] ?? context["orderID"]) as string | undefined;
                const transmissionId = (context["transmission_id"] ?? context["transmissionId"]) as string | undefined;
                const status = (context["status"] ?? context["rawStatus"]) as string | undefined;
                const badgeTone = RESULT_TONE[entry.result] ?? RESULT_TONE.default;
                return (
                  <tr
                    key={`${entry.loggedAt ?? "unknown"}-${index}`}
                    className="border-t border-border-light text-sm text-text-secondaryLight dark:border-border-dark dark:text-text-secondaryDark"
                  >
                    <td className="px-3 py-2 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                      {formatDateTime(entry.loggedAt)}
                    </td>
                    <td className="px-3 py-2">
                      <span className={clsx("inline-flex rounded-full px-2 py-0.5 text-xs font-semibold", badgeTone)}>
                        {entry.result}
                      </span>
                    </td>
                    <td className="px-3 py-2">
                      <div className="flex flex-col text-xs">
                        <span className="font-semibold text-text-primaryLight dark:text-text-primaryDark">
                          {orderId ?? "order 미확인"}
                        </span>
                        <span className="text-text-tertiaryLight dark:text-text-tertiaryDark">
                          {transmissionId ?? "transmission 미확인"}
                        </span>
                      </div>
                    </td>
                    <td className="px-3 py-2 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                      {status ?? "status 미확인"}
                    </td>
                    <td className="px-3 py-2 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                      {entry.message ?? "-"}
                    </td>
                    <td className="px-3 py-2 text-right">
                      <button
                        type="button"
                        onClick={() => handleReplay(transmissionId)}
                        className="inline-flex items-center rounded-lg border border-border-light px-3 py-1 text-xs font-semibold text-text-secondaryLight transition hover:bg-border-light/30 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-border-light dark:border-border-dark dark:text-text-secondaryDark dark:hover:bg-border-dark/40 dark:focus-visible:outline-border-dark"
                      >
                        재시도
                      </button>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
