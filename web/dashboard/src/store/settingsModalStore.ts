"use client";

import { create } from "zustand";

export type SettingsSection = "account" | "lightmem" | "proactive" | "general";

type SettingsModalState = {
  open: boolean;
  activeSection: SettingsSection;
  setActiveSection: (section: SettingsSection) => void;
  openModal: (section?: SettingsSection) => void;
  closeModal: () => void;
};

export const useSettingsModalStore = create<SettingsModalState>((set) => ({
  open: false,
  activeSection: "lightmem",
  setActiveSection: (section) => set({ activeSection: section }),
  openModal: (section = "lightmem") => set({ open: true, activeSection: section }),
  closeModal: () => set({ open: false }),
}));
