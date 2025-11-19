"use client";

import { create } from "zustand";

export type ToolAction = "TOOL_EVENT_STUDY" | "TOOL_DISCLOSURE" | "TOOL_NEWS";

type ToolParams = Record<string, unknown>;

type ToolStoreState = {
  isOpen: boolean;
  activeTool: ToolAction | null;
  params: ToolParams;
  openTool: (tool: ToolAction, params?: ToolParams) => void;
  closeTool: () => void;
};

export const useToolStore = create<ToolStoreState>((set) => ({
  isOpen: false,
  activeTool: null,
  params: {},
  openTool: (tool, params = {}) =>
    set({
      isOpen: true,
      activeTool: tool,
      params,
    }),
  closeTool: () =>
    set({
      isOpen: false,
      activeTool: null,
      params: {},
    }),
}));
