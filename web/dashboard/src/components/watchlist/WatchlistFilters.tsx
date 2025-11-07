import { useEffect, useMemo, useState } from "react";
import { CalendarClock, RefreshCw, Search } from "lucide-react";
import clsx from "clsx";

import { FilterChip } from "@/components/ui/FilterChip";
import { TagInput } from "@/components/ui/TagInput";
import { CompanyTickerInput } from "@/components/watchlist/CompanyTickerInput";

type WatchlistFiltersProps = {
  className?: string;
  selectedChannels: string[];
  onChannelsChange: (next: string[]) => void;
  selectedEventTypes: string[];
  onEventTypesChange: (next: string[]) => void;
  sentimentRange: [number, number];
  onSentimentRangeChange: (range: [number, number]) => void;
  selectedTickers: string[];
  onTickersChange: (next: string[]) => void;
  selectedRuleTags: string[];
  onRuleTagsChange: (next: string[]) => void;
  query: string;
  onQueryChange: (value: string) => void;
  windowOptions: Array<{ minutes: number; label: string }>;
  selectedWindowMinutes: number;
  onWindowMinutesChange: (minutes: number) => void;
  customWindowStart: string | null;
  customWindowEnd: string | null;
  onCustomWindowChange: (start: string | null, end: string | null) => void;
  isFetching?: boolean;
  onReset: () => void;
  availableTickers?: string[];
  availableRuleTags?: string[];
};

const CHANNEL_OPTIONS = [
  { value: "slack", label: "Slack" },
  { value: "email", label: "이메일" },
];

const EVENT_TYPE_OPTIONS = [
  { value: "filing", label: "공시" },
  { value: "news", label: "뉴스" },
];

const SENTIMENT_PRESETS: Array<{ label: string; range: [number, number] }> = [
  { label: "전체", range: [-1, 1] },
  { label: "부정↓", range: [-1, -0.3] },
  { label: "중립", range: [-0.3, 0.3] },
  { label: "긍정↑", range: [0.3, 1] },
];

const clampRange = (value: number, min: number, max: number) => Math.min(Math.max(value, min), max);

const toLocalDateTime = (value: string | null) => {
  if (!value) {
    return "";
  }
  try {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return "";
    }
    const formatted = date.toISOString().slice(0, 16);
    return formatted;
  } catch {
    return "";
  }
};

const toIsoString = (value: string) => {
  if (!value) {
    return null;
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return null;
  }
  return parsed.toISOString();
};

export function WatchlistFilters({
  className,
  selectedChannels,
  onChannelsChange,
  selectedEventTypes,
  onEventTypesChange,
  sentimentRange,
  onSentimentRangeChange,
  selectedTickers,
  onTickersChange,
  selectedRuleTags,
  onRuleTagsChange,
  query,
  onQueryChange,
  windowOptions,
  selectedWindowMinutes,
  onWindowMinutesChange,
  customWindowStart,
  customWindowEnd,
  onCustomWindowChange,
  isFetching = false,
  onReset,
  availableTickers = [],
  availableRuleTags = [],
}: WatchlistFiltersProps) {
  const [localQuery, setLocalQuery] = useState(query);

  useEffect(() => {
    setLocalQuery(query);
  }, [query]);

  useEffect(() => {
    const handle = window.setTimeout(() => {
      onQueryChange(localQuery.trim());
    }, localQuery ? 200 : 0);
    return () => {
      window.clearTimeout(handle);
    };
  }, [localQuery, onQueryChange]);

  const channelSet = useMemo(() => new Set(selectedChannels.map((value) => value.toLowerCase())), [selectedChannels]);
  const eventTypeSet = useMemo(() => new Set(selectedEventTypes.map((value) => value.toLowerCase())), [selectedEventTypes]);
  const isCustomRangeActive = Boolean(customWindowStart || customWindowEnd);

  const formattedStart = toLocalDateTime(customWindowStart);
  const formattedEnd = toLocalDateTime(customWindowEnd);

  const handleChannelToggle = (value: string) => {
    const normalized = value.toLowerCase();
    const next = channelSet.has(normalized)
      ? selectedChannels.filter((item) => item.toLowerCase() !== normalized)
      : [...selectedChannels, normalized];
    onChannelsChange(next);
  };

  const handleEventTypeToggle = (value: string) => {
    const normalized = value.toLowerCase();
    const next = eventTypeSet.has(normalized)
      ? selectedEventTypes.filter((item) => item.toLowerCase() !== normalized)
      : [...selectedEventTypes, normalized];
    onEventTypesChange(next);
  };

  const handleSentimentMinChange: React.ChangeEventHandler<HTMLInputElement> = (event) => {
    const nextMin = clampRange(Number(event.target.value), -1, sentimentRange[1]);
    onSentimentRangeChange([Math.min(nextMin, sentimentRange[1]), sentimentRange[1]]);
  };

  const handleSentimentMaxChange: React.ChangeEventHandler<HTMLInputElement> = (event) => {
    const nextMax = clampRange(Number(event.target.value), sentimentRange[0], 1);
    onSentimentRangeChange([sentimentRange[0], Math.max(nextMax, sentimentRange[0])]);
  };

  const handleWindowOptionClick = (minutes: number) => {
    onWindowMinutesChange(minutes);
    onCustomWindowChange(null, null);
  };

  const handleCustomStartChange: React.ChangeEventHandler<HTMLInputElement> = (event) => {
    const value = event.target.value.trim();
    onCustomWindowChange(toIsoString(value), customWindowEnd);
  };

  const handleCustomEndChange: React.ChangeEventHandler<HTMLInputElement> = (event) => {
    const value = event.target.value.trim();
    onCustomWindowChange(customWindowStart, toIsoString(value));
  };

  const activePreset = isCustomRangeActive ? null : selectedWindowMinutes;

  const renderSentimentLabel = (value: number) => `${value >= 0 ? "+" : ""}${value.toFixed(2)}`;

  return (
    <section
      className={clsx(
        "flex flex-col gap-6 rounded-2xl border border-border-light bg-background-cardLight p-6 shadow-card transition-colors dark:border-border-dark dark:bg-background-cardDark",
        className,
      )}
    >
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-text-primaryLight dark:text-text-primaryDark">알림 필터</h2>
          <p className="text-sm text-text-secondaryLight dark:text-text-secondaryDark">
            채널, 이벤트 유형, 감성 범위와 기간을 선택해 원하는 알림만 빠르게 찾아보세요.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {isFetching ? <RefreshCw className="h-4 w-4 animate-spin text-primary dark:text-primary.dark" aria-hidden /> : null}
          <button
            type="button"
            onClick={onReset}
            className="inline-flex items-center gap-2 rounded-lg border border-border-light px-3 py-1.5 text-sm font-semibold text-text-secondaryLight transition-colors hover:border-primary/40 hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40 dark:border-border-dark dark:text-text-secondaryDark dark:hover:border-primary.dark/40 dark:hover:text-primary.dark"
          >
            <RefreshCw className="h-4 w-4" aria-hidden />
            초기화
          </button>
        </div>
      </header>

      <div className="grid gap-6 md:grid-cols-2">
        <div className="space-y-4">
          <div className="space-y-2">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-text-secondaryLight dark:text-text-secondaryDark">채널</h3>
            <div className="flex flex-wrap gap-2">
              {CHANNEL_OPTIONS.map((option) => (
                <FilterChip
                  key={option.value}
                  active={channelSet.has(option.value)}
                  onClick={() => handleChannelToggle(option.value)}
                >
                  {option.label}
                </FilterChip>
              ))}
            </div>
          </div>

          <div className="space-y-2">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-text-secondaryLight dark:text-text-secondaryDark">
              이벤트 유형
            </h3>
            <div className="flex flex-wrap gap-2">
              {EVENT_TYPE_OPTIONS.map((option) => (
                <FilterChip
                  key={option.value}
                  active={eventTypeSet.has(option.value)}
                  onClick={() => handleEventTypeToggle(option.value)}
                >
                  {option.label}
                </FilterChip>
              ))}
            </div>
          </div>

          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-text-secondaryLight dark:text-text-secondaryDark">
                감성 범위
              </h3>
              <span className="text-xs font-semibold text-primary dark:text-primary.dark">
                {renderSentimentLabel(sentimentRange[0])} ~ {renderSentimentLabel(sentimentRange[1])}
              </span>
            </div>
            <div className="relative flex flex-col gap-3">
              <div className="relative h-2 rounded-full bg-border-light/70 dark:bg-border-dark/70">
                <div
                  className="absolute inset-y-0 rounded-full bg-gradient-to-r from-accent-negative/60 via-primary/70 to-accent-positive/60 transition-all"
                  style={{
                    left: `${((sentimentRange[0] + 1) / 2) * 100}%`,
                    right: `${(1 - (sentimentRange[1] + 1) / 2) * 100}%`,
                  }}
                />
              </div>
              <div className="flex flex-wrap items-center gap-4">
                <label className="flex items-center gap-2 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                  <span>최소</span>
                  <input
                    type="number"
                    inputMode="decimal"
                    step={0.05}
                    min={-1}
                    max={1}
                    value={sentimentRange[0]}
                    onChange={handleSentimentMinChange}
                    className="w-20 rounded-md border border-border-light bg-background-base px-2 py-1 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
                    aria-label="감성 최소값"
                  />
                </label>
                <span className="text-xs font-semibold text-text-secondaryLight dark:text-text-secondaryDark">~</span>
                <label className="flex items-center gap-2 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                  <span>최대</span>
                  <input
                    type="number"
                    inputMode="decimal"
                    step={0.05}
                    min={-1}
                    max={1}
                    value={sentimentRange[1]}
                    onChange={handleSentimentMaxChange}
                    className="w-20 rounded-md border border-border-light bg-background-base px-2 py-1 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
                    aria-label="감성 최대값"
                  />
                </label>
              </div>
              <div className="flex flex-wrap gap-2">
                {SENTIMENT_PRESETS.map((preset) => (
                  <FilterChip
                    key={preset.label}
                    active={preset.range[0] === sentimentRange[0] && preset.range[1] === sentimentRange[1]}
                    onClick={() => onSentimentRangeChange(preset.range)}
                  >
                    {preset.label}
                  </FilterChip>
                ))}
              </div>
            </div>
          </div>
        </div>

        <div className="space-y-5">
          <div className="space-y-2">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-text-secondaryLight dark:text-text-secondaryDark">
              종목 / 룰 태그
            </h3>
            <CompanyTickerInput
              values={selectedTickers}
              onChange={onTickersChange}
              placeholder="예: 삼성전자"
              aria-label="티커 필터"
              helperText="회사명을 입력하면 티커가 자동으로 채워집니다."
              staticOptions={availableTickers.map((ticker) => ({ ticker }))}
            />
            <TagInput
              values={selectedRuleTags}
              onChange={onRuleTagsChange}
              placeholder="룰 태그 입력 후 Enter"
              suggestions={availableRuleTags}
              aria-label="룰 태그 필터"
            />
          </div>

          <div className="space-y-2">
            <h3 className="text-xs font-semibold uppercase tracking-wide text-text-secondaryLight dark:text-text-secondaryDark">
              키워드 검색
            </h3>
            <div className="relative flex items-center rounded-lg border border-border-light bg-background-light px-3 py-2 transition-colors focus-within:border-primary focus-within:ring-2 focus-within:ring-primary/40 dark:border-border-dark dark:bg-background-dark">
              <Search className="mr-2 h-4 w-4 text-text-secondaryLight dark:text-text-secondaryDark" aria-hidden />
              <input
                type="text"
                value={localQuery}
                onChange={(event) => setLocalQuery(event.target.value)}
                placeholder="종목명, 룰 이름, 메시지 내용 검색"
                className="w-full bg-transparent text-sm text-text-primaryLight placeholder:text-text-secondaryLight focus:outline-none dark:text-text-primaryDark dark:placeholder:text-text-secondaryDark"
              />
            </div>
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-text-secondaryLight dark:text-text-secondaryDark">
                기간 선택
              </h3>
              {isCustomRangeActive ? (
                <span className="text-xs font-semibold text-primary dark:text-primary.dark">커스텀 범위 적용 중</span>
              ) : null}
            </div>
            <div className="flex flex-wrap gap-2">
              {windowOptions.map((option) => (
                <FilterChip
                  key={option.minutes}
                  active={!isCustomRangeActive && activePreset === option.minutes}
                  onClick={() => handleWindowOptionClick(option.minutes)}
                >
                  {option.label}
                </FilterChip>
              ))}
            </div>
            <div className="grid gap-3 rounded-lg border border-dashed border-border-light/70 bg-background-light/60 p-3 text-sm dark:border-border-dark/70 dark:bg-background-dark/60">
              <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-text-secondaryLight dark:text-text-secondaryDark">
                <CalendarClock className="h-4 w-4" aria-hidden />
                커스텀 기간
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                <label className="flex flex-col gap-1 text-xs font-semibold text-text-secondaryLight dark:text-text-secondaryDark">
                  시작
                  <input
                    type="datetime-local"
                    value={formattedStart}
                    onChange={handleCustomStartChange}
                    className="rounded-md border border-border-light bg-background-light px-2 py-1.5 text-sm text-text-primaryLight transition-colors focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/40 dark:border-border-dark dark:bg-background-dark dark:text-text-primaryDark"
                  />
                </label>
                <label className="flex flex-col gap-1 text-xs font-semibold text-text-secondaryLight dark:text-text-secondaryDark">
                  종료
                  <input
                    type="datetime-local"
                    value={formattedEnd}
                    onChange={handleCustomEndChange}
                    className="rounded-md border border-border-light bg-background-light px-2 py-1.5 text-sm text-text-primaryLight transition-colors focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/40 dark:border-border-dark dark:bg-background-dark dark:text-text-primaryDark"
                  />
                </label>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
