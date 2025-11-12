import { ChangeEvent } from "react";
import { shallow } from "zustand/shallow";
import { SECTOR_TAXONOMY, type SectorTaxonomyItem } from "@/constants/sectorTaxonomy";
import { useNewsFilterStore } from "@/store/newsFilterStore";

const SECTOR_OPTIONS = SECTOR_TAXONOMY;

const WINDOW_OPTIONS: { value: "1h" | "24h" | "7d"; label: string }[] = [
  { value: "1h", label: "최근 1시간" },
  { value: "24h", label: "최근 24시간" },
  { value: "7d", label: "최근 7일" },
];

export function NewsFilterPanel() {
  const {
    selectedSectors,
    negativeOnly,
    excludeNeutral,
    window,
    toggleSector,
    setNegativeOnly,
    setExcludeNeutral,
    setWindow,
  } = useNewsFilterStore(
    (state) => ({
      selectedSectors: state.selectedSectors,
      negativeOnly: state.negativeOnly,
      excludeNeutral: state.excludeNeutral,
      window: state.window,
      toggleSector: state.toggleSector,
      setNegativeOnly: state.setNegativeOnly,
      setExcludeNeutral: state.setExcludeNeutral,
      setWindow: state.setWindow,
    }),
    shallow,
  );

  const handleWindowChange = (event: ChangeEvent<HTMLSelectElement>) => {
    const value = event.target.value as typeof window;
    setWindow(value);
  };

  const renderSectorButton = (option: SectorTaxonomyItem) => {
    const { slug, label } = option;
    const isActive = selectedSectors.includes(slug);
    return (
      <button
        key={slug}
        type="button"
        onClick={() => toggleSector(slug)}
        className={`rounded-full border px-3 py-1 text-xs transition-colors ${
          isActive
            ? "border-primary bg-primary text-white"
            : "border-border-light text-text-secondaryLight hover:border-primary hover:text-primary dark:border-border-dark dark:text-text-secondaryDark dark:hover:border-primary.dark dark:hover:text-primary.dark"
        }`}
      >
        {label}
      </button>
    );
  };

  return (
    <aside className="rounded-xl border border-border-light bg-background-cardLight p-4 shadow-card transition-colors dark:border-border-dark dark:bg-background-cardDark">
      <h3 className="text-sm font-semibold">필터</h3>
      <div className="mt-3 space-y-4 text-sm">
        <section>
          <p className="text-xs font-semibold uppercase text-text-secondaryLight dark:text-text-secondaryDark">섹터</p>
          <div className="mt-2 flex flex-wrap gap-2">{SECTOR_OPTIONS.map(renderSectorButton)}</div>
        </section>

        <section>
          <p className="text-xs font-semibold uppercase text-text-secondaryLight dark:text-text-secondaryDark">감성 범위</p>
          <div className="mt-2 space-y-2 text-xs">
            <label className="flex items-center justify-between rounded-lg border border-border-light px-3 py-2 dark:border-border-dark">
              <span>부정만 보기</span>
              <input
                type="checkbox"
                checked={negativeOnly}
                onChange={(event) => setNegativeOnly(event.target.checked)}
                className="accent-primary"
              />
            </label>
            <label className="flex items-center justify-between rounded-lg border border-border-light px-3 py-2 dark:border-border-dark">
              <span>중립 제외</span>
              <input
                type="checkbox"
                checked={excludeNeutral}
                onChange={(event) => setExcludeNeutral(event.target.checked)}
                className="accent-primary"
              />
            </label>
          </div>
        </section>

        <section>
          <p className="text-xs font-semibold uppercase text-text-secondaryLight dark:text-text-secondaryDark">기간</p>
          <select
            value={window}
            onChange={handleWindowChange}
            className="w-full rounded-lg border border-border-light bg-transparent px-3 py-2 text-sm dark:border-border-dark"
          >
            {WINDOW_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </section>
      </div>
    </aside>
  );
}
