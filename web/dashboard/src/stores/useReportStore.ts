import { create } from "zustand";

export type ReportSource = {
  index?: number;
  title: string;
  url: string;
  date: string;
};

interface ReportState {
  isOpen: boolean;
  content: string;
  isGenerating: boolean;
  sources: ReportSource[];
  ticker?: string;
  reportId?: string;
  charts?: Record<string, unknown> | null;
  openPanel: () => void;
  closePanel: () => void;
  setContent: (content: string) => void;
  setGenerating: (status: boolean) => void;
  setSources: (sources: ReportSource[]) => void;
  setTicker: (ticker?: string) => void;
  setReportId: (id?: string) => void;
  setCharts: (charts?: Record<string, unknown> | null) => void;
  reset: () => void;
}

export const useReportStore = create<ReportState>((set) => ({
  isOpen: false,
  content: "",
  isGenerating: false,
  sources: [],
  ticker: undefined,
  reportId: undefined,
  charts: null,
  openPanel: () => set({ isOpen: true }),
  closePanel: () => set({ isOpen: false }),
  setContent: (content) => set({ content }),
  setGenerating: (status) => set({ isGenerating: status }),
  setSources: (sources) => set({ sources }),
  setTicker: (ticker) => set({ ticker }),
  setReportId: (reportId) => set({ reportId }),
  setCharts: (charts) => set({ charts: charts ?? null }),
  reset: () =>
    set({
      content: "",
      isGenerating: false,
      sources: [],
      ticker: undefined,
      reportId: undefined,
      charts: null,
    }),
}));
