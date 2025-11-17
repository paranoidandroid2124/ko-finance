import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  Clock,
  Loader2,
  Mail,
  Slack,
  X,
  XCircle,
} from "lucide-react";

import { useDispatchWatchlistDigest, useWatchlistRuleDetail } from "@/hooks/useAlerts";
import { formatDateTime } from "@/lib/date";
import type { WatchlistRadarItem, WatchlistRuleChannelSummary } from "@/lib/alertsApi";
import { useToastStore } from "@/store/toastStore";

type WatchlistDetailPanelProps = {
  item: WatchlistRadarItem | null;
  onClose: () => void;
};

const CHANNEL_ICON_MAP: Record<string, React.ComponentType<{ className?: string }>> = {
  slack: Slack,
  email: Mail,
};

const STATUS_LABEL: Record<string, string> = {
  delivered: "전송 성공",
  failed: "전송 실패",
};

export function WatchlistDetailPanel({ item, onClose }: WatchlistDetailPanelProps) {
  const ruleId = item?.ruleId ?? null;
  const {
    data,
    isLoading,
    isError,
    refetch,
  } = useWatchlistRuleDetail(ruleId, { recentLimit: 10 });
  const dispatchDigest = useDispatchWatchlistDigest();
  const showToast = useToastStore((state) => state.show);
  const [pendingChannel, setPendingChannel] = useState<"slack" | "email" | null>(null);
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const handler = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    const mediaQuery = window.matchMedia("(max-width: 768px)");
    const update = () => setIsMobile(mediaQuery.matches);
    update();
    if (typeof mediaQuery.addEventListener === "function") {
      mediaQuery.addEventListener("change", update);
      return () => mediaQuery.removeEventListener("change", update);
    }
    mediaQuery.addListener(update);
    return () => mediaQuery.removeListener(update);
  }, []);

  const rule = data?.rule;
  const deliveries = data?.recentDeliveries ?? [];
  const totalDeliveries = data?.totalDeliveries ?? 0;
  const failedDeliveries = data?.failedDeliveries ?? 0;
  const ruleChannels = useMemo<WatchlistRuleChannelSummary[]>(() => {
    if (!rule || !Array.isArray(rule.channels)) {
      return [];
    }
    return rule.channels;
  }, [rule]);
  const slackTargets = useMemo(() => {
    const collection = new Set<string>();
    ruleChannels
      .filter((channel) => channel.type.toLowerCase() === "slack")
      .forEach((channel) => {
        if (channel.target) {
          collection.add(channel.target);
        }
        (channel.targets ?? []).forEach((target) => {
          if (target) {
            collection.add(target);
          }
        });
      });
    return Array.from(collection);
  }, [ruleChannels]);
  const emailTargets = useMemo(() => {
    const collection = new Set<string>();
    ruleChannels
      .filter((channel) => channel.type.toLowerCase() === "email")
      .forEach((channel) => {
        if (channel.target) {
          collection.add(channel.target);
        }
        (channel.targets ?? []).forEach((target) => {
          if (target) {
            collection.add(target);
          }
        });
      });
    return Array.from(collection);
  }, [ruleChannels]);

  const statusTone = (item?.deliveryStatus ?? "").toLowerCase() === "failed" ? "negative" : "positive";

  const StatusIcon = statusTone === "negative" ? XCircle : CheckCircle2;
  const statusLabel = STATUS_LABEL[item?.deliveryStatus ?? ""] ?? "전송 상태";

  const handleResend = async (channel: "slack" | "email") => {
    if (channel === "slack" && slackTargets.length === 0) {
      showToast({
        intent: "warning",
        message: "재전송할 Slack 채널이 설정되어 있지 않습니다.",
      });
      return;
    }
    if (channel === "email" && emailTargets.length === 0) {
      showToast({
        intent: "warning",
        message: "재전송할 이메일 대상이 설정되어 있지 않습니다.",
      });
      return;
    }
    if (pendingChannel) {
      return;
    }
    setPendingChannel(channel);
    try {
      const windowMinutes = rule?.windowMinutes ?? 1440;
      const limit = 40;
      const result = await dispatchDigest.mutateAsync({
        windowMinutes,
        limit,
        slackTargets: channel === "slack" ? slackTargets : [],
        emailTargets: channel === "email" ? emailTargets : [],
      });
      const channelResult = result.results.find((entry) => entry.channel === channel);
      const delivered = channelResult?.delivered ?? 0;
      const failed = channelResult?.failed ?? 0;
      showToast({
        intent: failed > 0 ? "warning" : "success",
        message:
          channel === "slack"
            ? `Slack으로 ${delivered}건 재전송을 시도했어요. 실패 ${failed}건`
            : `이메일로 ${delivered}건 재전송을 시도했어요. 실패 ${failed}건`,
      });
    } catch (error) {
      const message =
        error instanceof Error ? error.message : "다이제스트 재전송에 실패했습니다.";
      showToast({
        intent: "error",
        message,
      });
    } finally {
      setPendingChannel(null);
    }
  };

  const handleLogRetry = (channel: string) => {
    const normalized = channel.toLowerCase();
    if ((normalized === "slack" && slackTargets.length > 0) || (normalized === "email" && emailTargets.length > 0)) {
      void handleResend(normalized as "slack" | "email");
    } else {
      showToast({
        intent: "warning",
        message: "전송 대상을 찾을 수 없어 재전송할 수 없습니다.",
      });
    }
  };

  const conditionChips = useMemo(() => {
    if (!rule) {
      return [];
    }
    const chips: Array<{ label: string; value: string }> = [];
    const condition = rule.condition;
    condition.tickers.forEach((ticker) => chips.push({ label: "티커", value: ticker }));
    condition.categories.forEach((category) => chips.push({ label: "카테고리", value: category }));
    condition.sectors.forEach((sector) => chips.push({ label: "섹터", value: sector }));
    if (condition.minSentiment != null) {
      chips.push({
        label: "감성 임계값",
        value: condition.minSentiment.toFixed(2),
      });
    }
    return chips;
  }, [rule]);

  if (!item || !ruleId) {
    return null;
  }

  const handleRetry = () => {
    void refetch();
  };

  return (
    <>
      <div
        className="fixed inset-0 z-40 bg-black/40 transition-opacity"
        aria-hidden="true"
        onClick={onClose}
      />
      <aside
        className={`fixed z-50 w-full overflow-y-auto bg-background-cardLight shadow-xl transition-transform dark:bg-background-cardDark ${
          isMobile
            ? "inset-x-0 bottom-0 top-auto h-[85vh] rounded-t-3xl border-t border-border-light dark:border-border-dark"
            : "inset-y-0 right-0 max-w-xl border-l border-border-light dark:border-border-dark"
        }`}
        aria-labelledby="watchlist-detail-title"
        role="dialog"
        aria-modal="true"
      >
        <header
          className={`flex items-start justify-between gap-3 border-b border-border-light px-6 py-5 dark:border-border-dark ${
            isMobile ? "pt-4" : ""
          }`}
        >
          {isMobile ? (
            <div className="absolute left-1/2 top-2 -translate-x-1/2">
              <span className="block h-1.5 w-12 rounded-full bg-border-light dark:bg-border-dark" />
            </div>
          ) : null}
          <div className="space-y-1">
            <p className="text-xs font-semibold uppercase tracking-wide text-text-secondaryLight dark:text-text-secondaryDark">
              워치리스트 상세
            </p>
            <h2
              id="watchlist-detail-title"
              className="text-xl font-semibold text-text-primaryLight dark:text-text-primaryDark"
            >
              {rule?.name ?? item.ruleName}
            </h2>
            <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
              {rule?.description ?? "워치리스트 룰 상세 정보입니다."}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-border-light text-text-secondaryLight transition hover:border-primary/40 hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/50 dark:border-border-dark dark:text-text-secondaryDark dark:hover:border-primary.dark/40 dark:hover:text-primary.dark"
            aria-label="상세 닫기"
          >
            <X className="h-4 w-4" aria-hidden />
          </button>
        </header>

        <section className="space-y-6 px-6 py-5">
          <div className="flex flex-wrap items-center gap-3">
            <span
              className={`inline-flex items-center gap-1 rounded-full px-3 py-1 text-xs font-semibold ring-1 ring-inset ${
                statusTone === "negative"
                  ? "bg-accent-negative/10 text-accent-negative ring-accent-negative/35"
                  : "bg-accent-positive/10 text-accent-positive ring-accent-positive/35"
              }`}
            >
              <StatusIcon className="h-3.5 w-3.5" aria-hidden />
              {statusLabel}
            </span>
            <span className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
              최근 전송 시각:{" "}
              {formatDateTime(item.deliveredAt, { includeSeconds: true, fallback: "알 수 없음" })}
            </span>
            <span className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
              총 전송 {totalDeliveries}건 · 실패 {failedDeliveries}건
            </span>
          </div>

          {isLoading ? (
            <div className="space-y-4">
              <div className="h-4 w-32 animate-pulse rounded bg-border-light/80 dark:bg-border-dark/80" />
              <div className="h-3 w-64 animate-pulse rounded bg-border-light/60 dark:bg-border-dark/60" />
              <div className="space-y-2">
                {Array.from({ length: 3 }).map((_, index) => (
                  <div key={index} className="h-20 animate-pulse rounded-lg bg-border-light/60 dark:bg-border-dark/60" />
                ))}
              </div>
            </div>
          ) : isError ? (
            <div className="rounded-lg border border-accent-negative/50 bg-accent-negative/10 p-4 text-sm text-accent-negative">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <AlertTriangle className="h-4 w-4" aria-hidden />
                  <span>룰 상세 정보를 불러오지 못했습니다.</span>
                </div>
                <button
                  type="button"
                  onClick={handleRetry}
                  className="rounded-md border border-accent-negative/50 px-2 py-1 text-xs font-semibold transition hover:bg-accent-negative/15"
                >
                  다시 시도
                </button>
              </div>
            </div>
          ) : rule ? (
            <>
              <section aria-label="빠른 액션" className="space-y-3">
                <h3 className="text-sm font-semibold text-text-primaryLight dark:text-text-primaryDark">
                  빠른 액션
                </h3>
                <div className="flex flex-wrap gap-2">
                  {slackTargets.length > 0 ? (
                    <button
                      type="button"
                      onClick={() => handleResend("slack")}
                      disabled={pendingChannel === "slack"}
                      className="inline-flex items-center gap-2 rounded-lg border border-primary px-3 py-1.5 text-xs font-semibold text-primary transition hover:bg-primary/10 disabled:cursor-not-allowed disabled:opacity-70 dark:border-primary.dark dark:text-primary.dark dark:hover:bg-primary.dark/10"
                    >
                      {pendingChannel === "slack" ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
                      ) : (
                        <Slack className="h-3.5 w-3.5" aria-hidden />
                      )}
                      Slack 재전송
                    </button>
                  ) : null}
                  {emailTargets.length > 0 ? (
                    <button
                      type="button"
                      onClick={() => handleResend("email")}
                      disabled={pendingChannel === "email"}
                      className="inline-flex items-center gap-2 rounded-lg border border-primary px-3 py-1.5 text-xs font-semibold text-primary transition hover:bg-primary/10 disabled:cursor-not-allowed disabled:opacity-70 dark:border-primary.dark dark:text-primary.dark dark:hover:bg-primary.dark/10"
                    >
                      {pendingChannel === "email" ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
                      ) : (
                        <Mail className="h-3.5 w-3.5" aria-hidden />
                      )}
                      이메일 재전송
                    </button>
                  ) : null}
                  {slackTargets.length === 0 && emailTargets.length === 0 ? (
                    <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                      재전송 가능한 채널이 없습니다. 룰 채널 설정을 확인해 주세요.
                    </p>
                  ) : null}
                </div>
              </section>

              <section aria-label="룰 조건" className="space-y-3">
                <h3 className="text-sm font-semibold text-text-primaryLight dark:text-text-primaryDark">
                  조건
                </h3>
                <div className="flex flex-wrap gap-2">
                  <span className="rounded-full border border-border-light px-3 py-1 text-xs font-semibold text-text-secondaryLight dark:border-border-dark dark:text-text-secondaryDark">
                    유형 · {rule.condition.type ? rule.condition.type.toUpperCase() : "UNKNOWN"}
                  </span>
                  {conditionChips.length > 0 ? (
                    conditionChips.map((chip, index) => (
                      <span
                        key={`${chip.label}-${chip.value}-${index}`}
                        className="rounded-full border border-border-light px-3 py-1 text-xs text-text-secondaryLight dark:border-border-dark dark:text-text-secondaryDark"
                      >
                        {chip.label} · {chip.value}
                      </span>
                    ))
                  ) : (
                    <span className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                      추가 조건 없음
                    </span>
                  )}
                </div>
              </section>

              <section aria-label="채널 설정" className="space-y-3">
                <h3 className="text-sm font-semibold text-text-primaryLight dark:text-text-primaryDark">
                  채널
                </h3>
                <div className="space-y-2">
                  {rule.channels.map((channel, index) => {
                    const IconComponent =
                      CHANNEL_ICON_MAP[channel.type.toLowerCase()] ?? Clock;
                    return (
                      <div
                        key={`${channel.type}-${index}`}
                        className="flex items-center justify-between gap-3 rounded-lg border border-border-light px-3 py-2 text-xs text-text-secondaryLight dark:border-border-dark dark:text-text-secondaryDark"
                      >
                        <div className="flex items-center gap-2">
                          <IconComponent className="h-4 w-4 text-primary dark:text-primary.dark" aria-hidden />
                          <span className="font-semibold text-text-primaryLight dark:text-text-primaryDark">
                            {channel.label ?? channel.type}
                          </span>
                        </div>
                        <div className="flex flex-wrap justify-end gap-2">
                          {channel.target ? (
                            <span className="rounded-full bg-border-light/60 px-2 py-0.5 dark:bg-border-dark/60">
                              {channel.target}
                            </span>
                          ) : null}
                          {channel.targets
                            .filter((target) => target !== channel.target)
                            .map((target) => (
                              <span
                                key={target}
                                className="rounded-full bg-border-light/60 px-2 py-0.5 dark:bg-border-dark/60"
                              >
                                {target}
                              </span>
                            ))}
                        </div>
                      </div>
                    );
                  })}
                  {rule.channels.length === 0 ? (
                    <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                      연결된 채널이 없습니다.
                    </p>
                  ) : null}
                </div>
              </section>

              <section aria-label="최근 전송 로그" className="space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-semibold text-text-primaryLight dark:text-text-primaryDark">
                    최근 전송 로그
                  </h3>
                  <span className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                    최대 {deliveries.length}건 표시
                  </span>
                </div>
                <div className="space-y-3">
                  {deliveries.length === 0 ? (
                    <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                      아직 수집된 전송 로그가 없습니다.
                    </p>
                  ) : (
                    deliveries.map((log) => {
                      const status = (log.status ?? "").toLowerCase();
                      const normalizedChannel = (log.channel ?? "").toLowerCase();
                      const LogIcon = status === "failed" ? XCircle : CheckCircle2;
                      const canRetry =
                        (normalizedChannel === "slack" && slackTargets.length > 0) ||
                        (normalizedChannel === "email" && emailTargets.length > 0);
                      return (
                        <div
                          key={log.deliveryId}
                          className="rounded-lg border border-border-light px-3 py-3 text-xs text-text-secondaryLight dark:border-border-dark dark:text-text-secondaryDark"
                        >
                          <div className="flex items-center justify-between gap-2">
                            <div className="flex items-center gap-2">
                              <LogIcon
                                className={`h-3.5 w-3.5 ${
                                  status === "failed"
                                    ? "text-accent-negative"
                                    : "text-accent-positive"
                                }`}
                                aria-hidden
                              />
                              <span className="font-semibold text-text-primaryLight dark:text-text-primaryDark">
                                {(normalizedChannel || "unknown").toUpperCase()}
                              </span>
                              <span>{STATUS_LABEL[status] ?? "상태 알 수 없음"}</span>
                            </div>
                            <div className="flex items-center gap-2">
                              <span>{formatDateTime(log.deliveredAt, { includeSeconds: true })}</span>
                              {status === "failed" && canRetry ? (
                                <button
                                  type="button"
                                  onClick={() => handleLogRetry(normalizedChannel)}
                                  className="rounded-md border border-accent-negative/50 px-2 py-0.5 text-[11px] font-semibold text-accent-negative transition hover:bg-accent-negative/15"
                                >
                                  다시 보내기
                                </button>
                              ) : null}
                            </div>
                          </div>
                          {log.error ? (
                            <p className="mt-2 flex items-center gap-1 text-accent-negative">
                              <AlertTriangle className="h-3 w-3" aria-hidden />
                              실패 사유: {log.error}
                            </p>
                          ) : null}
                          {log.events.length > 0 ? (
                            <div className="mt-3 space-y-2">
                              {log.events.map((event, index) => (
                                <div
                                  key={`${log.deliveryId}-event-${index}`}
                                  className="rounded-md border border-dashed border-border-light px-3 py-2 dark:border-border-dark"
                                >
                                  <div className="flex items-center justify-between gap-2">
                                    <span className="font-semibold text-text-primaryLight dark:text-text-primaryDark">
                                      {event.ticker ?? "종목 미상"}
                                    </span>
                                    <span>
                                      {formatDateTime(event.eventTime, { includeSeconds: false }) ??
                                        "발생 시각 미상"}
                                    </span>
                                  </div>
                                  <p className="mt-1 text-text-secondaryLight dark:text-text-secondaryDark">
                                    {event.headline ?? event.summary ?? "요약 정보 없음"}
                                  </p>
                                  <div className="mt-1 flex flex-wrap items-center gap-2 text-[11px] text-text-secondaryLight dark:text-text-secondaryDark">
                                    {event.sentiment != null ? (
                                      <span>감성 {event.sentiment.toFixed(2)}</span>
                                    ) : null}
                                    {event.category ? <span>분류 {event.category}</span> : null}
                                    {event.url ? (
                                      <a
                                        href={event.url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="font-semibold text-primary transition hover:underline dark:text-primary.dark"
                                      >
                                        원문 보기
                                      </a>
                                    ) : null}
                                  </div>
                                </div>
                              ))}
                            </div>
                          ) : null}
                        </div>
                      );
                    })
                  )}
                </div>
              </section>
            </>
          ) : null}
        </section>

        {isLoading ? (
          <div className="flex items-center justify-center gap-2 border-t border-border-light px-6 py-4 text-sm text-text-secondaryLight dark:border-border-dark dark:text-text-secondaryDark">
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
            상세 정보를 불러오는 중입니다...
          </div>
        ) : null}
      </aside>
    </>
  );
}

