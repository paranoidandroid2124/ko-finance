"use client";

import { createContext, useContext, useRef, type ReactNode } from "react";
import { createStore, type StoreApi } from "zustand";
import { useStore } from "zustand";

import type { EvidencePdfStatus } from "./types";

type EvidencePanelStoreState = {
  selectedUrnId?: string;
  hoveredUrnId?: string;
  diffActive: boolean;
  pdfStatus: EvidencePdfStatus;
  pdfError: string | null;
  setSelectedUrnId: (urnId?: string) => void;
  setHoveredUrnId: (urnId?: string) => void;
  setDiffActive: (value: boolean | ((prev: boolean) => boolean)) => void;
  setPdfState: (status: EvidencePdfStatus, error?: string | null) => void;
  reset: () => void;
};

const buildStore = (initial?: Partial<EvidencePanelStoreState>) =>
  createStore<EvidencePanelStoreState>((set) => ({
    selectedUrnId: initial?.selectedUrnId,
    hoveredUrnId: initial?.hoveredUrnId,
    diffActive: initial?.diffActive ?? false,
    pdfStatus: initial?.pdfStatus ?? "idle",
    pdfError: initial?.pdfError ?? null,
    setSelectedUrnId: (urnId) => set({ selectedUrnId: urnId }),
    setHoveredUrnId: (urnId) => set({ hoveredUrnId: urnId }),
    setDiffActive: (value) =>
      set((state) => ({
        diffActive: typeof value === "function" ? value(state.diffActive) : value,
      })),
    setPdfState: (status, error = null) => set({ pdfStatus: status, pdfError: error }),
    reset: () =>
      set({
        selectedUrnId: initial?.selectedUrnId,
        hoveredUrnId: initial?.hoveredUrnId,
        diffActive: initial?.diffActive ?? false,
        pdfStatus: "idle",
        pdfError: null,
      }),
  }));

const EvidencePanelStoreContext = createContext<StoreApi<EvidencePanelStoreState> | null>(null);

export function EvidencePanelStoreProvider({
  children,
  initialState,
}: {
  children: ReactNode;
  initialState?: Partial<EvidencePanelStoreState>;
}) {
  const storeRef = useRef<StoreApi<EvidencePanelStoreState>>();
  if (!storeRef.current) {
    storeRef.current = buildStore(initialState);
  }
  return (
    <EvidencePanelStoreContext.Provider value={storeRef.current}>{children}</EvidencePanelStoreContext.Provider>
  );
}

export function useEvidencePanelStore<T>(selector: (state: EvidencePanelStoreState) => T): T {
  const store = useContext(EvidencePanelStoreContext);
  if (!store) {
    throw new Error("EvidencePanelStoreProvider is missing.");
  }
  return useStore(store, selector);
}
