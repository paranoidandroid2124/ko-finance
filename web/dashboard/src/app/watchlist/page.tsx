"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  CalendarClock,
  CheckCircle2,
  ExternalLink,
  Loader2,
  Plus,
  Mail,
  RefreshCw,
  Slack,
  Sparkles,
  Star,
  StarOff,
  X,
  XCircle,
} from "lucide-react";

import { AppShell } from "@/components/layout/AppShell";
import { EventStudyExportButton } from "@/components/event-study/EventStudyExportButton";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { SkeletonBlock } from "@/components/ui/SkeletonBlock";
import { FilterChip } from "@/components/ui/FilterChip";
import { WatchlistFilters } from "@/components/watchlist/WatchlistFilters";
import { WatchlistDetailPanel } from "@/components/watchlist/WatchlistDetailPanel";
import { WatchlistRuleManager } from "@/components/watchlist/WatchlistRuleManager";
import { WatchlistRuleWizard } from "@/components/watchlist/WatchlistRuleWizard";
import { EventMatchList } from "@/components/watchlist/EventMatchList";
import { motion } from "framer-motion";
import {
  useWatchlistRadar,
  useDispatchWatchlistDigest,
  useAlertRules,
  useUpdateAlertRule,
  useDeleteAlertRule,
  useAlertEventMatches,
} from "@/hooks/useAlerts";
import { resolveCompanyIdentifier } from "@/hooks/useCompanySearch";
import {
  ApiError,
  type AlertChannelType,
  type AlertRule,
  type AlertEventMatch,
  type WatchlistRadarItem,
  type WatchlistDispatchResult,
  type WatchlistRuleDetail,
} from "@/lib/alertsApi";
import { formatDateTime } from "@/lib/date";
import { convertAlertRuleToDetail } from "@/components/watchlist/ruleDetail";
import { useToastStore } from "@/store/toastStore";
import { usePlanStore } from "@/store/planStore";
import { buildEventStudyExportParams } from "@/lib/eventStudyExport";

const WINDOW_OPTIONS = [
  { minutes: 180, label: "최근 3시간" },
  { minutes: 720, label: "최근 12시간" },
  { minutes: 1440, label: "최근 24시간" },
  { minutes: 10_080, label: "최근 7일" },
];

const CHANNEL_LABEL_MAP: Record<string, string> = {
  slack: "Slack",
  email: "이메일",
};

const EVENT_TYPE_LABEL_MAP: Record<string, string> = {
  filing: "공시",
  news: "뉴스",
};

type SortOption = "latest" | "sentiment" | "channel";
type GroupOption = "none" | "ticker" | "rule";

const SORT_OPTIONS: Array<{ value: SortOption; label: string }> = [
  { value: "latest", label: "최신순" },
  { value: "sentiment", label: "감성순" },
  { value: "channel", label: "채널명" },
];

const GROUP_OPTIONS: Array<{ value: GroupOption; label: string }> = [
  { value: "none", label: "묶지 않음" },
  { value: "ticker", label: "티커별" },
  { value: "rule", label: "룰별" },
];

const isAlertChannelType = (value: unknown): value is AlertChannelType =>
  value === "email" || value === "telegram" || value === "slack" || value === "webhook" || value === "pagerduty";

type DigestTargetType = "slack" | "email";

type DigestTargetEntry = {
  favorites: string[];
  recent: string[];
};

type DigestTargetStorage = Record<DigestTargetType, DigestTargetEntry>;

const DIGEST_TARGETS_STORAGE_KEY = "watchlist_digest_targets_v1";
const DIGEST_RECENT_LIMIT = 8;
const DIGEST_FAVORITE_LIMIT = 8;

const createDefaultDigestTargetStorage = (): DigestTargetStorage => ({
  slack: { favorites: [], recent: [] },
  email: { favorites: [], recent: [] },
});

const EMPTY_ITEMS: WatchlistRadarItem[] = [];

const normalizeTargetKey = (value: string) => value.trim().toLowerCase();

const sanitizeTargetList = (input: unknown): string[] =>
  Array.isArray(input)
    ? input
        .map((value) => String(value).trim())
        .filter((value) => value.length > 0)
    : [];

const dedupeTargets = (values: string[], limit: number): string[] => {
  const result: string[] = [];
  const seen = new Set<string>();
  for (const raw of values) {
    const trimmed = raw.trim();
    if (!trimmed) {
      continue;
    }
    const key = normalizeTargetKey(trimmed);
    if (seen.has(key)) {
      continue;
    }
    result.push(trimmed);
    seen.add(key);
    if (result.length >= limit) {
      break;
    }
  }
  return result;
};

const parseTargets = (value: string) =>
  value
    .split(/[\s,;]+/)
    .map((item) => item.trim())
    .filter((item) => item.length > 0);

const resolveTopChannel = (channels: Record<string, number> | undefined) => {
  if (!channels) {
    return null;
  }
  const [channel, count] =
    Object.entries(channels).sort((a, b) => {
      if (b[1] === a[1]) {
        return a[0].localeCompare(b[0]);
      }
      return b[1] - a[1];
    })[0] ?? [];
  if (!channel) {
    return null;
  }
  return { channel, count };
};

const renderTickerBadge = (ticker?: string | null) => {
  if (!ticker) {
    return null;
  }
  return (
    <span className="rounded-md border border-primary/30 bg-primary/10 px-2 py-0.5 text-xs font-semibold text-primary transition-colors group-hover:border-primary/50 group-hover:bg-primary/15 dark:border-primary.dark/35 dark:bg-primary.dark/15 dark:text-primary.dark">
      {ticker}
    </span>
  );
};

const renderSentimentBadge = (sentiment?: number | null) => {
  if (typeof sentiment !== "number") {
    return null;
  }
  let tone: "positive" | "negative" | "neutral" = "neutral";
  if (sentiment >= 0.3) {
    tone = "positive";
  } else if (sentiment <= -0.3) {
    tone = "negative";
  }

  const toneClass =
    tone === "positive"
      ? "bg-accent-positive/10 text-accent-positive ring-accent-positive/35"
      : tone === "negative"
        ? "bg-accent-negative/10 text-accent-negative ring-accent-negative/35"
        : "bg-border-light/40 text-text-secondaryLight ring-border-light/40 dark:bg-border-dark/50 dark:text-text-secondaryDark";

  const label =
    tone === "positive" ? "긍정" : tone === "negative" ? "부정" : "중립";

  return (
    <span className={`rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset transition-colors ${toneClass}`}>
      {label}
    </span>
  );
};

type WatchlistDigestItemProps = {
  item: WatchlistRadarItem;
  onSelect?: (item: WatchlistRadarItem) => void;
  isSelected?: boolean;
};

const WatchlistDigestItem = ({ item, onSelect, isSelected = false }: WatchlistDigestItemProps) => {
  const deliveredAt = formatDateTime(item.deliveredAt, { includeSeconds: true });
  const eventTime = formatDateTime(item.eventTime, {
    fallback: "발생 시각 미상",
  });
  const deliveryStatus = (item.deliveryStatus ?? "").toLowerCase();
  const isFailed = deliveryStatus === "failed";
  const statusIcon = isFailed ? (
    <XCircle className="h-3.5 w-3.5" aria-hidden />
  ) : (
    <CheckCircle2 className="h-3.5 w-3.5" aria-hidden />
  );
  const statusLabel = isFailed ? "전송 실패" : "전송 성공";
  const statusChipClass = isFailed
    ? "bg-accent-negative/10 text-accent-negative ring-accent-negative/35"
    : "bg-accent-positive/10 text-accent-positive ring-accent-positive/35";
  const cardToneClass = isFailed
    ? "border-accent-negative/50 bg-accent-negative/5 hover:border-accent-negative/70 focus-within:ring-accent-negative/40 dark:border-accent-negative/60 dark:bg-accent-negative/10"
    : "border-border-light bg-background-cardLight hover:border-primary/40 focus-within:ring-primary/40 dark:border-border-dark dark:bg-background-cardDark";
  const selectionClass = isSelected
    ? "ring-2 ring-primary/60 border-primary/60 dark:ring-primary.dark/60 dark:border-primary.dark/60"
    : "";
  const handleSelect = () => {
    onSelect?.(item);
  };

  return (
    <article
      role="button"
      tabIndex={0}
      aria-pressed={isSelected}
      onClick={handleSelect}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onSelect?.(item);
        }
      }}
      className={`group relative flex flex-col gap-4 overflow-hidden rounded-2xl border p-5 shadow-card transition-all hover:-translate-y-0.5 hover:shadow-lg cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/50 ${cardToneClass} ${selectionClass}`}
    >
      <header className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex items-center gap-2">
          {renderTickerBadge(item.ticker)}
          {item.company ? (
            <span className="text-sm font-semibold text-text-primaryLight dark:text-text-primaryDark">{item.company}</span>
          ) : null}
        </div>
        <div className="flex flex-wrap items-center gap-2 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
          <span className="rounded-md bg-border-light/50 px-2 py-0.5 capitalize dark:bg-border-dark/50">
            {CHANNEL_LABEL_MAP[item.channel] ?? item.channel}
          </span>
          <span>{deliveredAt}</span>
        </div>
      </header>

      <div className="flex flex-wrap items-center gap-2 text-xs font-semibold text-text-secondaryLight dark:text-text-secondaryDark">
        <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 ring-1 ring-inset ${statusChipClass}`}>
          {statusIcon}
          {statusLabel}
        </span>
        {item.ruleErrorCount > 0 ? (
          <span className="inline-flex items-center gap-1 rounded-full bg-accent-negative/15 px-2.5 py-1 text-accent-negative">
            실패 기록 {item.ruleErrorCount}회
          </span>
        ) : null}
        {isFailed && item.deliveryError ? (
          <span className="inline-flex items-center gap-1 text-accent-negative">
            <XCircle className="h-3 w-3" aria-hidden />
            {item.deliveryError}
          </span>
        ) : null}
      </div>

      <div>
        <h3 className="text-base font-semibold text-text-primaryLight transition-colors dark:text-text-primaryDark">
          {item.headline ?? item.summary ?? item.message ?? (isFailed ? "전송에 실패한 워치리스트 알림" : "워치리스트 알림")}
        </h3>
        <p className="mt-2 line-clamp-3 text-sm leading-relaxed text-text-secondaryLight transition-colors group-hover:text-text-primaryLight dark:text-text-secondaryDark">
          {item.summary ?? item.message ?? (isFailed ? "전송 오류가 발생했어요. 설정을 확인해 주세요." : "상세 요약이 제공되지 않은 알림입니다.")}
        </p>
      </div>
      <footer className="flex flex-wrap items-center justify-between gap-3 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
        <div className="flex flex-wrap items-center gap-2">
          {renderSentimentBadge(item.sentiment)}
          {item.category ? <span className="rounded-md border border-border-light px-2 py-0.5 dark:border-border-dark">{item.category}</span> : null}
          <span className="rounded-md border border-dashed border-border-light px-2 py-0.5 font-semibold dark:border-border-dark">
            {item.ruleName}
          </span>
          <span className="rounded-md bg-border-light/40 px-2 py-0.5 dark:bg-border-dark/40">{eventTime}</span>
        </div>
        {item.url ? (
          <a
            href={item.url}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(event) => {
              event.stopPropagation();
            }}
            className="flex items-center gap-1 text-xs font-semibold text-primary transition-transform hover:translate-x-0.5 dark:text-primary.dark"
          >
            원문 보기
            <ExternalLink className="h-3.5 w-3.5" aria-hidden />
          </a>
        ) : null}
      </footer>
    </article>
  );
};

type EventMatchPanelProps = {
  matches: AlertEventMatch[];
  loading: boolean;
};

const EventMatchPanel = ({ matches, loading }: EventMatchPanelProps) => (
  <section className="space-y-3 rounded-2xl border border-border-light bg-background-cardLight p-4 shadow-card dark:border-border-dark dark:bg-background-cardDark">
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div>
        <p className="text-xs font-semibold uppercase text-text-tertiaryLight dark:text-text-tertiaryDark">이벤트 매칭</p>
        <h2 className="text-lg font-semibold text-text-primaryLight dark:text-text-primaryDark">공시 이벤트 ↔ 워치리스트</h2>
        <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
          워치리스트 룰에 등록된 티커에서 감지된 공시 이벤트 매칭 로그입니다.
        </p>
      </div>
      <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">최근 {matches.length}건</p>
    </div>
    <EventMatchList
      matches={matches}
      loading={loading}
      limit={6}
      emptyMessage="워치리스트 룰에 등록된 티커에서 공시 이벤트가 감지되면 이곳에 표시됩니다."
    />
  </section>
);

export default function WatchlistRadarPage() {
  const defaultWindowMinutes = WINDOW_OPTIONS[2].minutes;
  const [targetStorage, setTargetStorage] = useState<DigestTargetStorage>(createDefaultDigestTargetStorage);
  const [selectedChannels, setSelectedChannels] = useState<string[]>([]);
  const [selectedEventTypes, setSelectedEventTypes] = useState<string[]>([]);
  const [sentimentRange, setSentimentRange] = useState<[number, number]>([-1, 1]);
  const [selectedTickers, setSelectedTickers] = useState<string[]>([]);
  const [selectedRuleTags, setSelectedRuleTags] = useState<string[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [windowMinutes, setWindowMinutes] = useState(defaultWindowMinutes);
  const [customWindow, setCustomWindow] = useState<{ start: string | null; end: string | null }>({
    start: null,
    end: null,
  });
  const [groupOption, setGroupOption] = useState<GroupOption>("none");
  const [sortOption, setSortOption] = useState<SortOption>("latest");
  const [selectedItem, setSelectedItem] = useState<WatchlistRadarItem | null>(null);
  const [isDetailOpen, setIsDetailOpen] = useState(false);
  const reportsEventExportEnabled = usePlanStore((state) => state.featureFlags.reportsEventExport);
  const [isWizardOpen, setIsWizardOpen] = useState(false);
  const [wizardMode, setWizardMode] = useState<"create" | "edit">("create");
  const [wizardInitialRule, setWizardInitialRule] = useState<WatchlistRuleDetail | null>(null);
  const [slackTargetsInput, setSlackTargetsInput] = useState("");
  const [emailTargetsInput, setEmailTargetsInput] = useState("");
  const [pendingChannel, setPendingChannel] = useState<"slack" | "email" | null>(null);
  const [lastResults, setLastResults] = useState<WatchlistDispatchResult[] | null>(null);
  const [lastDispatchedAt, setLastDispatchedAt] = useState<string | null>(null);
  const [mutatingRuleId, setMutatingRuleId] = useState<string | null>(null);
  const digestSectionRef = useRef<HTMLDivElement | null>(null);
  const [localRules, setLocalRules] = useState<AlertRule[]>([]);

  const {
    data: alertRulesData,
    isLoading: isRulesLoading,
    isError: isRulesError,
    refetch: refetchAlertRules,
  } = useAlertRules();
  const { data: eventMatchesData, isLoading: isEventMatchesLoading } = useAlertEventMatches({ limit: 10 });
  const updateRuleMutation = useUpdateAlertRule();
  const deleteRuleMutation = useDeleteAlertRule();
  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }
    try {
      const raw = window.localStorage.getItem(DIGEST_TARGETS_STORAGE_KEY);
      if (!raw) {
        return;
      }
      const parsed = JSON.parse(raw) as Partial<Record<DigestTargetType, Partial<DigestTargetEntry>>>;
      setTargetStorage({
        slack: {
          favorites: dedupeTargets(sanitizeTargetList(parsed?.slack?.favorites), DIGEST_FAVORITE_LIMIT),
          recent: dedupeTargets(sanitizeTargetList(parsed?.slack?.recent), DIGEST_RECENT_LIMIT),
        },
        email: {
          favorites: dedupeTargets(sanitizeTargetList(parsed?.email?.favorites), DIGEST_FAVORITE_LIMIT),
          recent: dedupeTargets(sanitizeTargetList(parsed?.email?.recent), DIGEST_RECENT_LIMIT),
        },
      });
    } catch {
      setTargetStorage(createDefaultDigestTargetStorage());
    }
  }, []);

  const updateTargetStorage = useCallback(
    (updater: (prev: DigestTargetStorage) => DigestTargetStorage) => {
      setTargetStorage((prev) => {
        const next = updater(prev);
        if (typeof window !== "undefined") {
          try {
            window.localStorage.setItem(DIGEST_TARGETS_STORAGE_KEY, JSON.stringify(next));
          } catch {
            // ignore persistence errors
          }
        }
        return next;
      });
    },
    [],
  );

  const recordRecentTargets = useCallback(
    (type: DigestTargetType, targets: string[]) => {
      if (targets.length === 0) {
        return;
      }
      updateTargetStorage((prev) => {
        const entry = prev[type];
        const favoriteKeys = new Set(entry.favorites.map(normalizeTargetKey));
        const seen = new Set<string>();
        const nextRecent: string[] = [];
        for (const raw of targets) {
          const trimmed = raw.trim();
          if (!trimmed) {
            continue;
          }
          const key = normalizeTargetKey(trimmed);
          if (favoriteKeys.has(key) || seen.has(key)) {
            continue;
          }
          nextRecent.push(trimmed);
          seen.add(key);
        }
        const mergedExisting = entry.recent.filter((value) => {
          const key = normalizeTargetKey(value);
          if (favoriteKeys.has(key) || seen.has(key)) {
            return false;
          }
          seen.add(key);
          return true;
        });
        const combined = [...nextRecent, ...mergedExisting];
        const deduped = dedupeTargets(combined, DIGEST_RECENT_LIMIT);
        if (
          deduped.length === entry.recent.length &&
          deduped.every((value, index) => entry.recent[index] === value)
        ) {
          return prev;
        }
        return {
          ...prev,
          [type]: {
            favorites: entry.favorites.slice(0, DIGEST_FAVORITE_LIMIT),
            recent: deduped,
          },
        };
      });
    },
    [updateTargetStorage],
  );

  const toggleFavoriteTarget = useCallback(
    (type: DigestTargetType, target: string) => {
      const trimmed = target.trim();
      if (!trimmed) {
        return;
      }
      const key = normalizeTargetKey(trimmed);
      updateTargetStorage((prev) => {
        const entry = prev[type];
        const existingIndex = entry.favorites.findIndex((value) => normalizeTargetKey(value) === key);
        let nextFavorites: string[];
        let nextRecents: string[];
        if (existingIndex >= 0) {
          const without = entry.favorites.filter((_, index) => index !== existingIndex);
          nextFavorites = dedupeTargets(without, DIGEST_FAVORITE_LIMIT);
          nextRecents = dedupeTargets([trimmed, ...entry.recent], DIGEST_RECENT_LIMIT);
        } else {
          nextFavorites = dedupeTargets([trimmed, ...entry.favorites], DIGEST_FAVORITE_LIMIT);
          nextRecents = entry.recent.filter((value) => normalizeTargetKey(value) !== key);
        }
        if (
          nextFavorites.length === entry.favorites.length &&
          nextFavorites.every((value, index) => entry.favorites[index] === value) &&
          nextRecents.length === entry.recent.length &&
          nextRecents.every((value, index) => entry.recent[index] === value)
        ) {
          return prev;
        }
        return {
          ...prev,
          [type]: {
            favorites: nextFavorites,
            recent: nextRecents,
          },
        };
      });
    },
    [updateTargetStorage],
  );

  const removeRecentTarget = useCallback(
    (type: DigestTargetType, target: string) => {
      const trimmed = target.trim();
      if (!trimmed) {
        return;
      }
      const key = normalizeTargetKey(trimmed);
      updateTargetStorage((prev) => {
        const entry = prev[type];
        const filtered = entry.recent.filter((value) => normalizeTargetKey(value) !== key);
        if (filtered.length === entry.recent.length) {
          return prev;
        }
        return {
          ...prev,
          [type]: {
            favorites: entry.favorites.slice(0, DIGEST_FAVORITE_LIMIT),
            recent: filtered,
          },
        };
      });
    },
    [updateTargetStorage],
  );

  const appendTargetToInput = useCallback(
    (type: DigestTargetType, target: string) => {
      const trimmed = target.trim();
      if (!trimmed) {
        return;
      }
      const setter = type === "slack" ? setSlackTargetsInput : setEmailTargetsInput;
      setter((prev) => {
        const tokens = parseTargets(prev);
        const normalized = new Set(tokens.map((value) => normalizeTargetKey(value)));
        if (normalized.has(normalizeTargetKey(trimmed))) {
          return prev;
        }
        const nextTokens = [...tokens, trimmed];
        return nextTokens.join(", ");
      });
    },
    [],
  );

  const mergeTargetsIntoInput = useCallback((current: string, additions: string[]) => {
    if (additions.length === 0) {
      return current;
    }
    const tokens = parseTargets(current);
    const normalized = new Set(tokens.map((value) => normalizeTargetKey(value)));
    const next = [...tokens];
    for (const raw of additions) {
      const trimmed = raw.trim();
      if (!trimmed) {
        continue;
      }
      const key = normalizeTargetKey(trimmed);
      if (normalized.has(key)) {
        continue;
      }
      normalized.add(key);
      next.push(trimmed);
    }
    return next.join(", ");
  }, []);

  const collectChannelTargets = useCallback((rule: AlertRule, type: DigestTargetType) => {
    if (!rule.channels?.length) {
      return [];
    }
    const collected: string[] = [];
    for (const channel of rule.channels) {
      if (channel.type !== type) {
        continue;
      }
      if (channel.target) {
        collected.push(channel.target);
      }
      if (Array.isArray(channel.targets)) {
        collected.push(...channel.targets);
      }
    }
    return dedupeTargets(collected, 16);
  }, []);

  const handleChannelsChange = useCallback((next: string[]) => {
    const normalized = Array.from(new Set(next.map((value) => value.toLowerCase())));
    setSelectedChannels(normalized);
  }, []);

  const handleEventTypesChange = useCallback((next: string[]) => {
    const normalized = Array.from(new Set(next.map((value) => value.toLowerCase())));
    setSelectedEventTypes(normalized);
  }, []);

  const handleTickersChange = useCallback((next: string[]) => {
    const normalized = Array.from(new Set(next.map((value) => value.toUpperCase())));
    setSelectedTickers(normalized);
  }, []);

  const handleRuleTagsChange = useCallback((next: string[]) => {
    const normalized = Array.from(new Set(next));
    setSelectedRuleTags(normalized);
  }, []);

  const handleQueryChange = useCallback((value: string) => {
    setSearchQuery(value);
  }, []);

  const handleWindowMinutesChange = useCallback((minutes: number) => {
    setWindowMinutes(minutes);
  }, []);

  const handleCustomWindowChange = useCallback((start: string | null, end: string | null) => {
    setCustomWindow({ start, end });
  }, []);

  const handleResetFilters = useCallback(() => {
    setSelectedChannels([]);
    setSelectedEventTypes([]);
    setSentimentRange([-1, 1]);
    setSelectedTickers([]);
    setSelectedRuleTags([]);
    setSearchQuery("");
    setWindowMinutes(defaultWindowMinutes);
    setCustomWindow({ start: null, end: null });
    setGroupOption("none");
    setSortOption("latest");
  }, [defaultWindowMinutes]);

  const handleSelectItem = useCallback((item: WatchlistRadarItem) => {
    setSelectedItem(item);
    setIsDetailOpen(true);
  }, []);

  const handleCloseDetail = useCallback(() => {
    setIsDetailOpen(false);
    setSelectedItem(null);
  }, []);

  const watchlistRequest = useMemo(() => {
    const [minSentimentValue, maxSentimentValue] = sentimentRange;
    const isSentimentDefault = minSentimentValue === -1 && maxSentimentValue === 1;
    const trimmedQuery = searchQuery.trim();
    return {
      windowMinutes,
      limit: 40,
      channels: selectedChannels,
      eventTypes: selectedEventTypes,
      tickers: selectedTickers,
      ruleTags: selectedRuleTags,
      minSentiment: isSentimentDefault ? null : minSentimentValue,
      maxSentiment: isSentimentDefault ? null : maxSentimentValue,
      query: trimmedQuery.length > 0 ? trimmedQuery : undefined,
      windowStart: customWindow.start,
      windowEnd: customWindow.end,
    };
  }, [
    sentimentRange,
    searchQuery,
    windowMinutes,
    selectedChannels,
    selectedEventTypes,
    selectedTickers,
    selectedRuleTags,
    customWindow,
  ]);

  const { data, isLoading, isFetching, isError, refetch } = useWatchlistRadar(watchlistRequest);
  const dispatchDigest = useDispatchWatchlistDigest();
  const showToast = useToastStore((state) => state.show);

  const numberFormatter = useMemo(() => new Intl.NumberFormat("ko-KR"), []);
  const summary = data?.summary;
  const items = data?.items ?? EMPTY_ITEMS;
  const generatedAt = formatDateTime(data?.generatedAt, { includeSeconds: true, fallback: "생성 시각 미상" });
  const generatedAtLabel = generatedAt ?? "생성 시각 미상";
  const alertPlanInfo = alertRulesData?.plan ?? null;
  const eventMatches = eventMatchesData?.matches ?? [];
  const buildWatchlistExportParams = useCallback(() => {
    const now = new Date();
    const windowDuration = windowMinutes || defaultWindowMinutes;
    const inferredStart = customWindow.start ? new Date(customWindow.start) : new Date(now.getTime() - windowDuration * 60 * 1000);
    const inferredEnd = customWindow.end ? new Date(customWindow.end) : now;
    const resolvedSearch = searchQuery.trim() || selectedTickers[0] || undefined;
    return buildEventStudyExportParams({
      windowStart: -5,
      windowEnd: 20,
      scope: "market",
      significance: 0.1,
      startDate: inferredStart,
      endDate: inferredEnd,
      search: resolvedSearch,
      limit: 200,
    });
  }, [customWindow.end, customWindow.start, defaultWindowMinutes, searchQuery, selectedTickers, windowMinutes]);

  useEffect(() => {
    if (alertRulesData?.items) {
      setLocalRules(alertRulesData.items);
    }
  }, [alertRulesData?.items]);
  const availableTickers = useMemo(() => {
    const collection = new Set<string>();
    for (const item of items) {
      if (item.ticker) {
        collection.add(item.ticker.toUpperCase());
      }
      (item.ruleTickers ?? []).forEach((ticker) => {
        if (ticker) {
          collection.add(String(ticker).toUpperCase());
        }
      });
    }
    return Array.from(collection).sort((a, b) => a.localeCompare(b));
  }, [items]);
  const availableRuleTags = useMemo(() => {
    const collection = new Set<string>();
    for (const item of items) {
      (item.ruleTags ?? []).forEach((tag) => {
        if (tag) {
          collection.add(String(tag));
        }
      });
    }
    return Array.from(collection).sort((a, b) => a.localeCompare(b, "ko"));
  }, [items]);
  const slackFavorites = targetStorage.slack.favorites;
  const slackRecents = targetStorage.slack.recent;
  const emailFavorites = targetStorage.email.favorites;
  const emailRecents = targetStorage.email.recent;
  const slackFavoriteKeys = useMemo(
    () => new Set(slackFavorites.map(normalizeTargetKey)),
    [slackFavorites],
  );
  const emailFavoriteKeys = useMemo(
    () => new Set(emailFavorites.map(normalizeTargetKey)),
    [emailFavorites],
  );
  const sortedItems = useMemo(() => {
    const toTimestamp = (value: string | null | undefined) => {
      if (!value) {
        return 0;
      }
      const time = Date.parse(value);
      return Number.isNaN(time) ? 0 : time;
    };
    const cloned = [...items];
    if (sortOption === "sentiment") {
      cloned.sort((a, b) => {
        const aValue = typeof a.sentiment === "number" ? a.sentiment : -Infinity;
        const bValue = typeof b.sentiment === "number" ? b.sentiment : -Infinity;
        if (bValue !== aValue) {
          return bValue - aValue;
        }
        return toTimestamp(b.deliveredAt) - toTimestamp(a.deliveredAt);
      });
      return cloned;
    }
    if (sortOption === "channel") {
      cloned.sort((a, b) => {
        const channelCompare = (a.channel ?? "").localeCompare(b.channel ?? "");
        if (channelCompare !== 0) {
          return channelCompare;
        }
        return toTimestamp(b.deliveredAt) - toTimestamp(a.deliveredAt);
      });
      return cloned;
    }
    cloned.sort((a, b) => toTimestamp(b.deliveredAt) - toTimestamp(a.deliveredAt));
    return cloned;
  }, [items, sortOption]);
  const groupedItems = useMemo(() => {
    if (sortedItems.length === 0) {
      return [] as Array<{ key: string; label: string | null; items: WatchlistRadarItem[] }>;
    }
    if (groupOption === "none") {
      return [
        {
          key: "all",
          label: null,
          items: sortedItems,
        },
      ];
    }
    const groups = new Map<string, { label: string; items: WatchlistRadarItem[] }>();
    sortedItems.forEach((entry) => {
      const key = groupOption === "ticker" ? entry.ticker ?? "기타" : entry.ruleName ?? "미분류";
      const label =
        groupOption === "ticker" ? `티커 · ${entry.ticker ?? "기타"}` : `룰 · ${entry.ruleName ?? "미분류"}`;
      const existing = groups.get(key);
      if (existing) {
        existing.items.push(entry);
      } else {
        groups.set(key, { label, items: [entry] });
      }
    });
    return Array.from(groups.entries()).map(([key, value]) => ({
      key: `${groupOption}:${key}`,
      label: value.label,
      items: value.items,
    }));
  }, [groupOption, sortedItems]);
  useEffect(() => {
    if (!selectedItem) {
      return;
    }
    const updated = items.find((entry) => entry.deliveryId === selectedItem.deliveryId);
    if (!updated) {
      setSelectedItem(null);
      setIsDetailOpen(false);
      return;
    }
    if (updated !== selectedItem) {
      setSelectedItem(updated);
    }
  }, [items, selectedItem]);
  const activeFilters = useMemo(
    () =>
      [
        selectedChannels.length > 0
          ? {
              key: "channels",
              label: "채널",
              value: selectedChannels.map((value) => CHANNEL_LABEL_MAP[value] ?? value).join(", "),
              onRemove: () => handleChannelsChange([]),
            }
          : null,
        selectedEventTypes.length > 0
          ? {
              key: "eventTypes",
              label: "유형",
              value: selectedEventTypes.map((value) => EVENT_TYPE_LABEL_MAP[value] ?? value).join(", "),
              onRemove: () => handleEventTypesChange([]),
            }
          : null,
        !(sentimentRange[0] === -1 && sentimentRange[1] === 1)
          ? {
              key: "sentiment",
              label: "감성",
              value: `${sentimentRange[0].toFixed(2)} ~ ${sentimentRange[1].toFixed(2)}`,
              onRemove: () => setSentimentRange([-1, 1]),
            }
          : null,
        selectedTickers.length > 0
          ? {
              key: "tickers",
              label: "티커",
              value: selectedTickers.join(", "),
              onRemove: () => handleTickersChange([]),
            }
          : null,
        selectedRuleTags.length > 0
          ? {
              key: "ruleTags",
              label: "태그",
              value: selectedRuleTags.join(", "),
              onRemove: () => handleRuleTagsChange([]),
            }
          : null,
        searchQuery.trim().length > 0
          ? {
              key: "query",
              label: "검색",
              value: searchQuery.trim(),
              onRemove: () => handleQueryChange(""),
            }
          : null,
        customWindow.start || customWindow.end
          ? {
              key: "customWindow",
              label: "기간",
              value: `${formatDateTime(customWindow.start, { includeTime: false, fallback: "시작 미지정" })} ~ ${formatDateTime(customWindow.end, { includeTime: false, fallback: "현재" })}`,
              onRemove: () => {
                handleCustomWindowChange(null, null);
                handleWindowMinutesChange(defaultWindowMinutes);
              },
            }
          : windowMinutes !== defaultWindowMinutes
            ? {
                key: "window",
                label: "기간",
                value:
                  WINDOW_OPTIONS.find((option) => option.minutes === windowMinutes)?.label ??
                  `최근 ${windowMinutes}분`,
                onRemove: () => handleWindowMinutesChange(defaultWindowMinutes),
              }
            : null,
      ].filter((entry): entry is { key: string; label: string; value: string; onRemove: () => void } => entry !== null),
    [
      selectedChannels,
      selectedEventTypes,
      sentimentRange,
      selectedTickers,
      selectedRuleTags,
      searchQuery,
      customWindow,
      windowMinutes,
      handleChannelsChange,
      handleEventTypesChange,
      handleTickersChange,
      handleRuleTagsChange,
      handleQueryChange,
      handleCustomWindowChange,
      handleWindowMinutesChange,
      defaultWindowMinutes,
      setSentimentRange,
    ],
  );

  const effectiveWindowMinutes = data?.windowMinutes ?? windowMinutes;
  const hours = effectiveWindowMinutes / 60;
  const windowLabel = (() => {
    if (hours >= 24 && Number.isInteger(hours / 24)) {
      return `${(hours / 24).toFixed(0)}일`;
    }
    if (hours >= 1) {
      return `${hours % 1 === 0 ? hours.toFixed(0) : hours.toFixed(1)}시간`;
    }
    return `${effectiveWindowMinutes}분`;
  })();
  const windowStartLabel = formatDateTime(summary?.windowStart, { includeTime: false, fallback: "시작 미상" });
  const windowEndLabel = formatDateTime(summary?.windowEnd, { includeTime: false, fallback: "현재" });

  const handleOpenWizard = () => {
    setWizardMode("create");
    setWizardInitialRule(null);
    setIsWizardOpen(true);
  };

  const handleCloseWizard = () => {
    setIsWizardOpen(false);
    setWizardInitialRule(null);
    setWizardMode("create");
  };

  const handleRefresh = useCallback(() => {
    void refetch();
  }, [refetch]);

  const handleWizardCompleted = () => {
    setIsWizardOpen(false);
    setWizardMode("create");
    setWizardInitialRule(null);
    handleRefresh();
    void refetchAlertRules();
  };

  const handleEditRuleFromManager = useCallback(
    (rule: AlertRule) => {
      setWizardMode("edit");
      setWizardInitialRule(convertAlertRuleToDetail(rule));
      setIsWizardOpen(true);
    },
    [convertAlertRuleToDetail],
  );

  const handleToggleRuleFromManager = useCallback(
    async (rule: AlertRule) => {
      const nextStatus = rule.status === "active" ? "paused" : "active";
      setMutatingRuleId(rule.id);
      try {
        await updateRuleMutation.mutateAsync({ id: rule.id, payload: { status: nextStatus } });
        showToast({
          intent: "success",
          message: nextStatus === "active" ? "알림을 다시 활성화했습니다." : "알림을 일시 중지했습니다.",
        });
        setLocalRules((prev) =>
          prev.map((item) => (item.id === rule.id ? { ...item, status: nextStatus } : item)),
        );
        void refetchAlertRules();
        handleRefresh();
      } catch (error) {
        const message =
          error instanceof ApiError
            ? error.message
            : error instanceof Error
              ? error.message
              : "알림 상태를 변경하지 못했어요.";
        showToast({
          intent: "error",
          message,
        });
      } finally {
        setMutatingRuleId(null);
      }
    },
    [handleRefresh, refetchAlertRules, showToast, updateRuleMutation],
  );

  const handleDeleteRuleFromManager = useCallback(
    async (rule: AlertRule) => {
      setMutatingRuleId(rule.id);
      try {
        await deleteRuleMutation.mutateAsync(rule.id);
        showToast({
          intent: "success",
          message: `${rule.name} 알림을 삭제했습니다.`,
        });
        setLocalRules((prev) => prev.filter((item) => item.id !== rule.id));
        void refetchAlertRules();
        handleRefresh();
      } catch (error) {
        const message =
          error instanceof ApiError
            ? error.message
            : error instanceof Error
              ? error.message
              : "알림을 삭제하지 못했어요.";
        showToast({
          intent: "error",
          message,
        });
      } finally {
        setMutatingRuleId(null);
      }
    },
    [deleteRuleMutation, handleRefresh, refetchAlertRules, showToast],
  );

  const handleShareRuleToDigest = useCallback(
    async (rule: AlertRule) => {
      const rawTickers = Array.from(
        new Set(
          (rule.trigger?.tickers ?? [])
            .map((value) => String(value).trim())
            .filter((value) => value.length > 0),
        ),
      );

      if (rawTickers.length > 0) {
        try {
          const resolvedTickers = await Promise.all(
            rawTickers.map(async (candidate) => {
              try {
                const resolved = await resolveCompanyIdentifier(candidate);
                const ticker = resolved?.ticker?.trim();
                if (ticker) {
                  return ticker.toUpperCase();
                }
              } catch {
                // ignore individual resolution errors
              }
              return candidate.toUpperCase();
            }),
          );
          setSelectedTickers(Array.from(new Set(resolvedTickers)));
        } catch {
          setSelectedTickers(Array.from(new Set(rawTickers.map((value) => value.toUpperCase()))));
        }
      } else {
        setSelectedTickers([]);
      }

      const categories = Array.from(
        new Set(
          (rule.trigger?.categories ?? [])
            .map((value) => String(value).trim())
            .filter((value) => value.length > 0),
        ),
      );
      setSelectedRuleTags(categories);

      const conditionType = rule.trigger?.type;
      setSelectedEventTypes(conditionType ? [conditionType] : []);

      const channelTypes = Array.from(
        new Set(
          (rule.channels ?? [])
            .map((channel) => channel.type)
            .filter((value): value is AlertChannelType => isAlertChannelType(value)),
        ),
      );
      setSelectedChannels(channelTypes);

      setWindowMinutes(rule.frequency?.windowMinutes || defaultWindowMinutes);
      setCustomWindow({ start: null, end: null });

      const slackTargetsFromRule = collectChannelTargets(rule, "slack");
      if (slackTargetsFromRule.length > 0) {
        setSlackTargetsInput((prev) => mergeTargetsIntoInput(prev, slackTargetsFromRule));
        recordRecentTargets("slack", slackTargetsFromRule);
      }
      const emailTargetsFromRule = collectChannelTargets(rule, "email");
      if (emailTargetsFromRule.length > 0) {
        setEmailTargetsInput((prev) => mergeTargetsIntoInput(prev, emailTargetsFromRule));
        recordRecentTargets("email", emailTargetsFromRule);
      }

      setSelectedItem(null);
      setIsDetailOpen(false);
      digestSectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      showToast({
        intent: "info",
        message: "다이제스트 패널에 선택한 룰의 필터와 채널을 불러왔어요.",
      });
    },
    [
      collectChannelTargets,
      defaultWindowMinutes,
      mergeTargetsIntoInput,
      recordRecentTargets,
      showToast,
    ],
  );

  const handleDispatch = async (channel: "slack" | "email") => {
    const slackTargets = parseTargets(slackTargetsInput);
    const emailTargets = parseTargets(emailTargetsInput);

    if (channel === "slack" && slackTargets.length === 0) {
      showToast({
        intent: "warning",
        message: "전달할 Slack 채널을 입력해 주세요. 예: #watchlist-radar",
      });
      return;
    }
    if (channel === "email" && emailTargets.length === 0) {
      showToast({
        intent: "warning",
        message: "전달할 이메일 주소를 입력해 주세요.",
      });
      return;
    }

    setPendingChannel(channel);
    try {
      const result = await dispatchDigest.mutateAsync({
        windowMinutes,
        limit: 40,
        slackTargets: channel === "slack" ? slackTargets : [],
        emailTargets: channel === "email" ? emailTargets : [],
      });
      setLastResults(result.results);
      setLastDispatchedAt(new Date().toISOString());
      if (channel === "slack") {
        recordRecentTargets("slack", slackTargets);
      } else {
        recordRecentTargets("email", emailTargets);
      }

      const channelResult = result.results.find((entry) => entry.channel === channel);
      const delivered = channelResult?.delivered ?? 0;
      const failed = channelResult?.failed ?? 0;

      showToast({
        intent: failed > 0 ? "warning" : "success",
        message:
          channel === "slack"
            ? `Slack으로 ${numberFormatter.format(delivered)}건 전송을 시도했어요. 실패 ${failed}건`
            : `이메일로 ${numberFormatter.format(delivered)}건 전송을 시도했어요. 실패 ${failed}건`,
      });
    } catch (error) {
      const message =
        error instanceof ApiError
          ? error.message
          : error instanceof Error
            ? error.message
            : "워치리스트 다이제스트 전송에 실패했습니다.";
      showToast({
        intent: "error",
        message,
      });
    } finally {
      setPendingChannel(null);
    }
  };

  if (isError) {
    return (
      <AppShell>
        <ErrorState
          title="워치리스트 레이더 데이터를 불러오지 못했어요."
          description="네트워크 상태를 확인한 뒤 다시 시도해 주세요."
          action={
            <button
              type="button"
              onClick={handleRefresh}
              className="inline-flex items-center gap-2 rounded-lg border border-primary/50 px-4 py-2 text-sm font-semibold text-primary transition-colors hover:bg-primary/10 dark:border-primary.dark/50 dark:text-primary.dark dark:hover:bg-primary.dark/10"
            >
              <RefreshCw className="h-4 w-4" aria-hidden />
              다시 시도
            </button>
          }
        />
        <WatchlistDetailPanel item={isDetailOpen ? selectedItem : null} onClose={handleCloseDetail} />
      </AppShell>
    );
  }

  const topTickerLabel = (summary?.topTickers ?? []).slice(0, 3).join(", ");
  const topChannel = resolveTopChannel(summary?.topChannels);
  const topFailureChannel = resolveTopChannel(summary?.channelFailures);
  const failedDeliveries = summary?.failedDeliveries ?? 0;
  const totalDeliveries = summary?.totalDeliveries ?? 0;
  const uniqueTickers = summary?.uniqueTickers ?? 0;
  const primaryChannelLabel = topChannel ? CHANNEL_LABEL_MAP[topChannel.channel] ?? topChannel.channel : null;

  const quickStats = [
    {
      title: "최근 알림",
      value: `${numberFormatter.format(totalDeliveries)}건`,
      helper: `최근 ${windowLabel} 동안 수신`,
    },
    {
      title: "커버된 종목",
      value: `${numberFormatter.format(uniqueTickers)}개`,
      helper: topTickerLabel ? `주요: ${topTickerLabel}` : "최근 알림 기준",
    },
    {
      title: "주요 채널",
      value: primaryChannelLabel ?? "—",
      helper: primaryChannelLabel
        ? `${numberFormatter.format(topChannel?.count ?? 0)}회`
        : "최근 집계 없음",
    },
  ];

  return (
    <AppShell>
      <section className="flex flex-col gap-4 rounded-2xl border border-border-light bg-background-cardLight p-6 shadow-card transition-colors dark:border-border-dark dark:bg-background-cardDark">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div className="space-y-1">
            <div className="inline-flex items-center gap-2 rounded-full bg-primary/10 px-3 py-1 text-xs font-semibold text-primary dark:bg-primary.dark/15 dark:text-primary.dark">
              <Sparkles className="h-3.5 w-3.5" aria-hidden />
              내 워치리스트
            </div>
            <h1 className="text-2xl font-semibold text-text-primaryLight dark:text-text-primaryDark">워치리스트 레이더</h1>
            <p className="text-sm leading-relaxed text-text-secondaryLight dark:text-text-secondaryDark">
              내가 저장한 워치리스트 룰에서 울린 알림을 한눈에 모아 확인하세요. 필요하다면 Slack이나 이메일로 바로 공유할 수 있어요.
            </p>
        </div>
        <div className="flex items-center gap-2">
          {isFetching ? <Loader2 className="h-5 w-5 animate-spin text-primary dark:text-primary.dark" aria-hidden /> : null}
          <motion.button
            type="button"
            whileTap={{ scale: 0.94 }}
            whileHover={{ scale: 1.03 }}
            onClick={handleOpenWizard}
            className="inline-flex items-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm font-semibold text-white shadow transition-transform focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40 dark:bg-primary.dark"
          >
            <Plus className="h-4 w-4" aria-hidden />
            알림 룰 생성
          </motion.button>
          <button
            type="button"
            onClick={handleRefresh}
            className="inline-flex items-center gap-2 rounded-lg border border-border-light px-3 py-2 text-sm font-semibold text-text-primaryLight transition-all hover:border-primary/40 hover:text-primary dark:border-border-dark dark:text-text-primaryDark dark:hover:border-primary.dark/40 dark:hover:text-primary.dark"
          >
            <RefreshCw className="h-4 w-4" aria-hidden />
            새로 고침
          </button>
          {reportsEventExportEnabled ? (
            <EventStudyExportButton
              buildParams={buildWatchlistExportParams}
              variant="secondary"
              size="sm"
              className="rounded-lg"
            >
              이벤트 리포트
            </EventStudyExportButton>
          ) : null}
        </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <CalendarClock className="h-4 w-4 text-text-secondaryLight dark:text-text-secondaryDark" aria-hidden />
          <span className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">
            {`${windowLabel} 윈도우 · ${windowStartLabel} ~ ${windowEndLabel} · 생성 ${generatedAtLabel}`}
          </span>
        </div>
      </section>

      <WatchlistRuleManager
        plan={alertPlanInfo}
        rules={localRules}
        isLoading={isRulesLoading}
        isError={isRulesError}
        mutatingRuleId={mutatingRuleId}
        onCreate={handleOpenWizard}
        onEdit={handleEditRuleFromManager}
        onToggle={handleToggleRuleFromManager}
        onDelete={handleDeleteRuleFromManager}
        onShareToDigest={handleShareRuleToDigest}
      />

      {failedDeliveries > 0 ? (
        <div className="flex items-start gap-3 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800 dark:border-amber-500/40 dark:bg-amber-500/10 dark:text-amber-100">
          <XCircle className="mt-0.5 h-4 w-4 flex-shrink-0" aria-hidden />
          <div className="space-y-1">
            <p className="font-semibold">최근 전송 실패 {numberFormatter.format(failedDeliveries)}건이 감지됐어요.</p>
            <p className="text-xs leading-relaxed">
              Slack·이메일 연결 상태를 확인하거나{" "}
              <a href="/admin?section=watchlist" className="font-semibold underline decoration-dotted">
                운영 콘솔
              </a>
              에서 실패 로그와 재전송 옵션을 살펴보세요.
            </p>
            {topFailureChannel ? (
              <p className="text-xs">
                가장 많은 실패 채널: {CHANNEL_LABEL_MAP[topFailureChannel.channel] ?? topFailureChannel.channel} (
                {numberFormatter.format(topFailureChannel.count)}회)
              </p>
            ) : null}
          </div>
        </div>
      ) : null}

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {isLoading
          ? Array.from({ length: 3 }).map((_, index) => (
              <SkeletonBlock key={`watchlist-stat-skeleton-${index}`} lines={4} />
            ))
          : quickStats.map((stat) => (
              <div
                key={stat.title}
                className="rounded-2xl border border-border-light bg-background-cardLight p-4 shadow-card dark:border-border-dark dark:bg-background-cardDark"
              >
                <p className="text-xs font-semibold uppercase tracking-wide text-text-secondaryLight dark:text-text-secondaryDark">
                  {stat.title}
                </p>
                <p className="mt-2 text-2xl font-semibold text-text-primaryLight dark:text-text-primaryDark">{stat.value}</p>
                <p className="mt-1 text-xs text-text-secondaryLight dark:text-text-secondaryDark">{stat.helper}</p>
              </div>
            ))}
      </section>

      <EventMatchPanel matches={eventMatches} loading={isEventMatchesLoading} />

      <WatchlistFilters
        selectedChannels={selectedChannels}
        onChannelsChange={handleChannelsChange}
        selectedEventTypes={selectedEventTypes}
        onEventTypesChange={handleEventTypesChange}
        sentimentRange={sentimentRange}
        onSentimentRangeChange={setSentimentRange}
        selectedTickers={selectedTickers}
        onTickersChange={handleTickersChange}
        selectedRuleTags={selectedRuleTags}
        onRuleTagsChange={handleRuleTagsChange}
        query={searchQuery}
        onQueryChange={handleQueryChange}
        windowOptions={WINDOW_OPTIONS}
        selectedWindowMinutes={windowMinutes}
        onWindowMinutesChange={handleWindowMinutesChange}
        customWindowStart={customWindow.start}
        customWindowEnd={customWindow.end}
        onCustomWindowChange={handleCustomWindowChange}
        isFetching={isFetching}
        onReset={handleResetFilters}
        availableTickers={availableTickers}
        availableRuleTags={availableRuleTags}
      />

      <section className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-border-light bg-background-cardLight p-4 shadow-card transition-colors dark:border-border-dark dark:bg-background-cardDark">
        <div className="flex flex-col gap-2">
          <span className="text-xs font-semibold uppercase tracking-wide text-text-secondaryLight dark:text-text-secondaryDark">
            정렬 기준
          </span>
          <div className="flex flex-wrap gap-2">
            {SORT_OPTIONS.map((option) => (
              <FilterChip
                key={option.value}
                active={sortOption === option.value}
                onClick={() => setSortOption(option.value)}
              >
                {option.label}
              </FilterChip>
            ))}
          </div>
        </div>
        <div className="flex flex-col gap-2">
          <span className="text-xs font-semibold uppercase tracking-wide text-text-secondaryLight dark:text-text-secondaryDark">
            묶음 보기
          </span>
          <div className="flex flex-wrap gap-2">
            {GROUP_OPTIONS.map((option) => (
              <FilterChip
                key={option.value}
                active={groupOption === option.value}
                onClick={() => setGroupOption(option.value)}
              >
                {option.label}
              </FilterChip>
            ))}
          </div>
        </div>
      </section>

      {activeFilters.length > 0 ? (
        <section className="flex flex-wrap items-center gap-2 rounded-2xl border border-border-light bg-background-cardLight p-4 text-sm shadow-card transition-colors dark:border-border-dark dark:bg-background-cardDark">
          <span className="text-xs font-semibold uppercase tracking-wide text-text-secondaryLight dark:text-text-secondaryDark">
            적용된 필터
          </span>
          {activeFilters.map((filter) => (
            <FilterChip
              key={filter.key}
              active
              onClick={filter.onRemove}
              aria-label={`${filter.label} 필터 해제`}
            >
              <span className="text-sm font-medium text-text-primaryLight dark:text-text-primaryDark">
                {filter.label}: {filter.value}
              </span>
              <X className="h-3.5 w-3.5 text-primary dark:text-primary.dark" aria-hidden />
            </FilterChip>
          ))}
        </section>
      ) : null}

      {isLoading ? (
        <section className="grid gap-4 lg:grid-cols-[2fr,1fr]">
          <SkeletonBlock lines={6} className="h-60" />
          <SkeletonBlock lines={6} className="h-60" />
        </section>
      ) : (
        <section className="grid gap-6 lg:grid-cols-[2fr,1fr]">
          <div className="space-y-6">
            {groupedItems.length === 0 || groupedItems.every((group) => group.items.length === 0) ? (
              <EmptyState
                title="아직 워치리스트 알림이 없어요."
                description="하루 동안 울린 워치리스트 룰이 없었습니다. 룰 윈도우나 조건을 조정해 보거나 조금 뒤에 다시 확인해 주세요."
              />
            ) : (
              groupedItems.map((group) => (
                <div key={group.key} className="space-y-3">
                  {group.label ? (
                    <div className="flex items-center justify-between">
                      <h3 className="text-sm font-semibold text-text-primaryLight dark:text-text-primaryDark">
                        {group.label}
                      </h3>
                      <span className="text-[11px] text-text-secondaryLight dark:text-text-secondaryDark">
                        {group.items.length}건
                      </span>
                    </div>
                  ) : null}
                  <div className="space-y-4">
                    {group.items.map((entry) => (
                      <WatchlistDigestItem
                        key={entry.deliveryId}
                        item={entry}
                        onSelect={handleSelectItem}
                        isSelected={isDetailOpen && selectedItem?.deliveryId === entry.deliveryId}
                      />
                    ))}
                  </div>
                </div>
              ))
            )}
          </div>

          <aside
            ref={digestSectionRef}
            className="flex flex-col gap-5 rounded-2xl border border-border-light bg-background-cardLight p-5 shadow-card transition-colors dark:border-border-dark dark:bg-background-cardDark"
          >
            <div>
              <h2 className="text-lg font-semibold text-text-primaryLight dark:text-text-primaryDark">다이제스트 전송</h2>
              <p className="mt-1 text-sm text-text-secondaryLight dark:text-text-secondaryDark">
                슬랙 채널이나 이메일로 워치리스트 알림 요약을 보낼 수 있어요. 전송 대상은 쉼표 또는 줄바꿈으로 구분해 입력하세요.
              </p>
            </div>
            <div className="space-y-3">
              <label className="flex flex-col gap-1">
                <span className="text-xs font-semibold uppercase tracking-wide text-text-secondaryLight dark:text-text-secondaryDark">
                  Slack 채널
                </span>
                <div className="relative flex items-center gap-2 rounded-lg border border-border-light bg-background-light px-3 py-2 transition-all focus-within:border-primary focus-within:ring-2 focus-within:ring-primary/40 dark:border-border-dark dark:bg-background-dark">
                  <Slack className="h-4 w-4 text-primary dark:text-primary.dark" aria-hidden />
                  <input
                    value={slackTargetsInput}
                    onChange={(event) => setSlackTargetsInput(event.target.value)}
                    placeholder="#watchlist-radar, #ops-alerts"
                    className="w-full bg-transparent text-sm text-text-primaryLight outline-none placeholder:text-text-secondaryLight focus:outline-none dark:text-text-primaryDark dark:placeholder:text-text-secondaryDark"
                  />
                </div>
              </label>
              {slackFavorites.length > 0 ? (
                <div className="space-y-1">
                  <p className="text-[11px] font-semibold uppercase tracking-wide text-text-secondaryLight dark:text-text-secondaryDark">
                    즐겨찾기
                  </p>
                  <div className="flex flex-wrap items-center gap-2">
                    {slackFavorites.map((value) => (
                      <div key={`slack-favorite-${value}`} className="flex items-center gap-1">
                        <FilterChip onClick={() => appendTargetToInput("slack", value)}>{value}</FilterChip>
                        <button
                          type="button"
                          onClick={() => toggleFavoriteTarget("slack", value)}
                          className="inline-flex h-6 w-6 items-center justify-center rounded-full text-primary transition-colors hover:bg-primary/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40 dark:text-primary.dark dark:hover:bg-primary.dark/15"
                          aria-label={`${value} 즐겨찾기 해제`}
                        >
                          <Star className="h-3.5 w-3.5 fill-current" aria-hidden />
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}
              {slackRecents.length > 0 ? (
                <div className="space-y-1">
                  <p className="text-[11px] font-semibold uppercase tracking-wide text-text-secondaryLight dark:text-text-secondaryDark">
                    최근 사용
                  </p>
                  <div className="flex flex-wrap items-center gap-2">
                    {slackRecents.map((value) => {
                      const normalized = normalizeTargetKey(value);
                      const isFavorite = slackFavoriteKeys.has(normalized);
                      return (
                        <div key={`slack-recent-${value}`} className="flex items-center gap-1">
                          <FilterChip onClick={() => appendTargetToInput("slack", value)}>{value}</FilterChip>
                          <button
                            type="button"
                            onClick={() => toggleFavoriteTarget("slack", value)}
                            className="inline-flex h-6 w-6 items-center justify-center rounded-full text-text-secondaryLight transition-colors hover:bg-border-light focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40 dark:text-text-secondaryDark dark:hover:bg-border-dark"
                            aria-label={isFavorite ? `${value} 즐겨찾기 해제` : `${value} 즐겨찾기에 추가`}
                          >
                            {isFavorite ? (
                              <Star className="h-3.5 w-3.5 text-primary dark:text-primary.dark" aria-hidden />
                            ) : (
                              <StarOff className="h-3.5 w-3.5" aria-hidden />
                            )}
                          </button>
                          {!isFavorite ? (
                            <button
                              type="button"
                              onClick={() => removeRecentTarget("slack", value)}
                              className="inline-flex h-6 w-6 items-center justify-center rounded-full text-text-secondaryLight transition-colors hover:bg-border-light focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40 dark:text-text-secondaryDark dark:hover:bg-border-dark"
                              aria-label={`${value} 최근 목록에서 제거`}
                            >
                              <X className="h-3.5 w-3.5" aria-hidden />
                            </button>
                          ) : null}
                        </div>
                      );
                    })}
                  </div>
                </div>
              ) : null}
              <button
                type="button"
                onClick={() => handleDispatch("slack")}
                disabled={pendingChannel === "slack"}
                className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white shadow transition-transform hover:-translate-y-0.5 hover:shadow-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/60 disabled:cursor-not-allowed disabled:opacity-70 dark:bg-primary.dark"
              >
                {pendingChannel === "slack" ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : <Slack className="h-4 w-4" aria-hidden />}
                Slack으로 보내기
              </button>
            </div>

            <div className="space-y-3">
              <label className="flex flex-col gap-1">
                <span className="text-xs font-semibold uppercase tracking-wide text-text-secondaryLight dark:text-text-secondaryDark">
                  이메일
                </span>
                <div className="relative flex items-center gap-2 rounded-lg border border-border-light bg-background-light px-3 py-2 transition-all focus-within:border-primary focus-within:ring-2 focus-within:ring-primary/40 dark:border-border-dark dark:bg-background-dark">
                  <Mail className="h-4 w-4 text-primary dark:text-primary.dark" aria-hidden />
                  <input
                    value={emailTargetsInput}
                    onChange={(event) => setEmailTargetsInput(event.target.value)}
                    placeholder="ops@example.com, ceo@example.com"
                    className="w-full bg-transparent text-sm text-text-primaryLight outline-none placeholder:text-text-secondaryLight focus:outline-none dark:text-text-primaryDark dark:placeholder:text-text-secondaryDark"
                  />
                </div>
              </label>
              {emailFavorites.length > 0 ? (
                <div className="space-y-1">
                  <p className="text-[11px] font-semibold uppercase tracking-wide text-text-secondaryLight dark:text-text-secondaryDark">
                    즐겨찾기
                  </p>
                  <div className="flex flex-wrap items-center gap-2">
                    {emailFavorites.map((value) => (
                      <div key={`email-favorite-${value}`} className="flex items-center gap-1">
                        <FilterChip onClick={() => appendTargetToInput("email", value)}>{value}</FilterChip>
                        <button
                          type="button"
                          onClick={() => toggleFavoriteTarget("email", value)}
                          className="inline-flex h-6 w-6 items-center justify-center rounded-full text-primary transition-colors hover:bg-primary/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40 dark:text-primary.dark dark:hover:bg-primary.dark/15"
                          aria-label={`${value} 즐겨찾기 해제`}
                        >
                          <Star className="h-3.5 w-3.5 fill-current" aria-hidden />
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}
              {emailRecents.length > 0 ? (
                <div className="space-y-1">
                  <p className="text-[11px] font-semibold uppercase tracking-wide text-text-secondaryLight dark:text-text-secondaryDark">
                    최근 사용
                  </p>
                  <div className="flex flex-wrap items-center gap-2">
                    {emailRecents.map((value) => {
                      const normalized = normalizeTargetKey(value);
                      const isFavorite = emailFavoriteKeys.has(normalized);
                      return (
                        <div key={`email-recent-${value}`} className="flex items-center gap-1">
                          <FilterChip onClick={() => appendTargetToInput("email", value)}>{value}</FilterChip>
                          <button
                            type="button"
                            onClick={() => toggleFavoriteTarget("email", value)}
                            className="inline-flex h-6 w-6 items-center justify-center rounded-full text-text-secondaryLight transition-colors hover:bg-border-light focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40 dark:text-text-secondaryDark dark:hover:bg-border-dark"
                            aria-label={isFavorite ? `${value} 즐겨찾기 해제` : `${value} 즐겨찾기에 추가`}
                          >
                            {isFavorite ? (
                              <Star className="h-3.5 w-3.5 text-primary dark:text-primary.dark" aria-hidden />
                            ) : (
                              <StarOff className="h-3.5 w-3.5" aria-hidden />
                            )}
                          </button>
                          {!isFavorite ? (
                            <button
                              type="button"
                              onClick={() => removeRecentTarget("email", value)}
                              className="inline-flex h-6 w-6 items-center justify-center rounded-full text-text-secondaryLight transition-colors hover:bg-border-light focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40 dark:text-text-secondaryDark dark:hover:bg-border-dark"
                              aria-label={`${value} 최근 목록에서 제거`}
                            >
                              <X className="h-3.5 w-3.5" aria-hidden />
                            </button>
                          ) : null}
                        </div>
                      );
                    })}
                  </div>
                </div>
              ) : null}
              <button
                type="button"
                onClick={() => handleDispatch("email")}
                disabled={pendingChannel === "email"}
                className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-gradient-to-r from-primary/90 to-primary px-4 py-2 text-sm font-semibold text-white shadow transition-transform hover:-translate-y-0.5 hover:shadow-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/60 disabled:cursor-not-allowed disabled:opacity-70 dark:from-primary.dark/90 dark:to-primary.dark"
              >
                {pendingChannel === "email" ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : <Mail className="h-4 w-4" aria-hidden />}
                이메일로 보내기
              </button>
            </div>

            <div className="rounded-lg border border-dashed border-border-light/70 bg-background-light/40 p-3 text-xs text-text-secondaryLight dark:border-border-dark/70 dark:bg-background-dark/40 dark:text-text-secondaryDark">
              <p className="font-semibold text-text-primaryLight dark:text-text-primaryDark">전송 현황</p>
              <p className="mt-1">
                {lastDispatchedAt
                  ? `마지막 전송: ${formatDateTime(lastDispatchedAt, { includeSeconds: true })}`
                  : "아직 전송한 기록이 없습니다."}
              </p>
              {lastResults && lastResults.length > 0 ? (
                <ul className="mt-2 space-y-1">
                  {lastResults.map((result) => (
                    <li key={result.channel} className="flex items-center justify-between">
                      <span className="uppercase tracking-wide text-text-secondaryLight dark:text-text-secondaryDark">{result.channel}</span>
                      <span className="font-semibold text-text-primaryLight dark:text-text-primaryDark">
                        {numberFormatter.format(result.delivered)}건 전달 · 실패 {numberFormatter.format(result.failed)}건
                      </span>
                    </li>
                  ))}
                </ul>
              ) : null}
            </div>
          </aside>
        </section>
      )}
      <WatchlistRuleWizard
        open={isWizardOpen}
        mode={wizardMode}
        initialRule={wizardInitialRule}
        onClose={handleCloseWizard}
        onCompleted={handleWizardCompleted}
      />
      <WatchlistDetailPanel item={isDetailOpen ? selectedItem : null} onClose={handleCloseDetail} />
    </AppShell>
  );
}
