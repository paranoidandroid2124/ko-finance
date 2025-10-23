import { create } from "zustand";

export type NewsWindowOption = "1h" | "24h" | "7d";

type NewsFilterState = {
  selectedSectors: string[];
  negativeOnly: boolean;
  excludeNeutral: boolean;
  window: NewsWindowOption;
  toggleSector: (sector: string) => void;
  setNegativeOnly: (value: boolean) => void;
  setExcludeNeutral: (value: boolean) => void;
  setWindow: (value: NewsWindowOption) => void;
  reset: () => void;
};

const DEFAULT_STATE: Pick<NewsFilterState, "selectedSectors" | "negativeOnly" | "excludeNeutral" | "window"> = {
  selectedSectors: [],
  negativeOnly: false,
  excludeNeutral: false,
  window: "24h",
};

export const useNewsFilterStore = create<NewsFilterState>((set) => ({
  ...DEFAULT_STATE,
  toggleSector: (sector) =>
    set((state) => {
      const normalized = sector.trim();
      if (!normalized) {
        return state;
      }
      const isSelected = state.selectedSectors.includes(normalized);
      return {
        ...state,
        selectedSectors: isSelected
          ? state.selectedSectors.filter((item) => item !== normalized)
          : [...state.selectedSectors, normalized],
      };
    }),
  setNegativeOnly: (value) => set({ negativeOnly: value }),
  setExcludeNeutral: (value) => set({ excludeNeutral: value }),
  setWindow: (value) => set({ window: value }),
  reset: () => set({ ...DEFAULT_STATE }),
}));

export const selectNewsFilterOptions = (state: NewsFilterState) => ({
  sectors: state.selectedSectors,
  negativeOnly: state.negativeOnly,
  excludeNeutral: state.excludeNeutral,
  window: state.window,
});
