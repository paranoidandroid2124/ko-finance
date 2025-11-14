"use client";

import { useMemo } from "react";

const DATE_PRESETS = [
  { value: "7d", label: "최근 7일" },
  { value: "30d", label: "최근 30일" },
  { value: "90d", label: "최근 90일" },
  { value: "custom", label: "사용자 지정" },
] as const;

const SECTOR_OPTIONS = [
  { value: "semiconductor", label: "반도체" },
  { value: "technology", label: "테크" },
  { value: "finance", label: "금융" },
  { value: "bio", label: "바이오" },
  { value: "energy", label: "에너지" },
];

export type DatePreset = (typeof DATE_PRESETS)[number]["value"];

export type SearchFilterState = {
  datePreset: DatePreset;
  customFrom?: string;
  customTo?: string;
  sectors: string[];
};

type SearchFiltersSidebarProps = {
  filters: SearchFilterState;
  onChange: (next: SearchFilterState) => void;
};

export function SearchFiltersSidebar({ filters, onChange }: SearchFiltersSidebarProps) {
  const hasCustomRange = filters.datePreset === "custom";
  const activeSectors = useMemo(() => new Set(filters.sectors.map((sector) => sector.toLowerCase())), [filters.sectors]);

  const handlePresetChange = (preset: DatePreset) => {
    if (preset === filters.datePreset) {
      return;
    }
    onChange({
      ...filters,
      datePreset: preset,
    });
  };

  const handleCustomChange = (field: "customFrom" | "customTo", value: string) => {
    onChange({
      ...filters,
      datePreset: "custom",
      [field]: value,
    });
  };

  const toggleSector = (slug: string) => {
    const normalized = slug.toLowerCase();
    const sectors = new Set(activeSectors);
    if (sectors.has(normalized)) {
      sectors.delete(normalized);
    } else {
      sectors.add(normalized);
    }
    onChange({
      ...filters,
      sectors: Array.from(sectors),
    });
  };

  return (
    <aside className="space-y-6 rounded-2xl border border-border-light bg-background-cardLight p-4 shadow-card dark:border-border-dark dark:bg-background-cardDark">
      <div>
        <h2 className="text-sm font-semibold text-text-primaryLight dark:text-text-primaryDark">날짜 범위</h2>
        <div className="mt-3 space-y-2 text-sm">
          {DATE_PRESETS.map((preset) => (
            <label key={preset.value} className="flex items-center gap-2">
              <input
                type="radio"
                name="search-date-preset"
                value={preset.value}
                checked={filters.datePreset === preset.value}
                onChange={() => handlePresetChange(preset.value)}
              />
              <span>{preset.label}</span>
            </label>
          ))}
          {hasCustomRange ? (
            <div className="mt-3 space-y-2 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
              <div className="flex flex-col gap-1">
                <label>시작일</label>
                <input
                  type="date"
                  className="rounded-lg border border-border-light bg-transparent px-2 py-1 text-text-primaryLight dark:border-border-dark dark:text-text-primaryDark"
                  value={filters.customFrom ?? ""}
                  onChange={(event) => handleCustomChange("customFrom", event.target.value)}
                />
              </div>
              <div className="flex flex-col gap-1">
                <label>종료일</label>
                <input
                  type="date"
                  className="rounded-lg border border-border-light bg-transparent px-2 py-1 text-text-primaryLight dark:border-border-dark dark:text-text-primaryDark"
                  value={filters.customTo ?? ""}
                  onChange={(event) => handleCustomChange("customTo", event.target.value)}
                />
              </div>
            </div>
          ) : null}
        </div>
      </div>

      <div>
        <h2 className="text-sm font-semibold text-text-primaryLight dark:text-text-primaryDark">섹터</h2>
        <div className="mt-3 flex flex-wrap gap-2">
          {SECTOR_OPTIONS.map((option) => {
            const isActive = activeSectors.has(option.value);
            return (
              <button
                key={option.value}
                type="button"
                onClick={() => toggleSector(option.value)}
                className={`rounded-full border px-3 py-1 text-xs font-semibold transition ${
                  isActive
                    ? "border-primary bg-primary/10 text-primary dark:border-primary.dark dark:bg-primary.dark/20 dark:text-primary.dark"
                    : "border-border-light text-text-secondaryLight hover:border-primary hover:text-primary dark:border-border-dark dark:text-text-secondaryDark"
                }`}
              >
                {option.label}
              </button>
            );
          })}
        </div>
      </div>
    </aside>
  );
}
