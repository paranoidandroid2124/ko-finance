"use client";

import { nanoid } from "nanoid";
import { create } from "zustand";

import type { CommanderRouteDecision } from "@/lib/chatApi";
import { postToolMemoryWrite, type ToolMemoryWritePayload } from "@/lib/chatApi";
import { resolveToolByCallName, type CommanderToolId } from "@/components/tools/registry";
import { useChatStore, type ToolAttachment } from "@/store/chatStore";

type ToolMemoryDraft = Omit<ToolMemoryWritePayload, "sessionId" | "turnId" | "toolId"> & {
  toolId: CommanderToolId | string;
};

type ToolInvocationContext = {
  sessionId: string | null;
  turnId?: string | null;
  assistantMessageId?: string | null;
};

type ToolInvocation = {
  toolId: CommanderToolId;
  params: Record<string, unknown>;
  paywall: CommanderRouteDecision["paywall"];
  requiresContext: string[];
  decision?: CommanderRouteDecision | null;
  sessionId: string | null;
  turnId?: string | null;
  assistantMessageId?: string | null;
  memoryDraft?: ToolMemoryDraft | null;
};

type ToolStoreState = {
  isOpen: boolean;
  entry: ToolInvocation | null;
  toolContexts: Record<string, string[]>;
  openFromDecision: (decision: CommanderRouteDecision, context: ToolInvocationContext) => void;
  openTool: (toolId: CommanderToolId, params?: Record<string, unknown>) => void;
  setMemoryDraft: (draft: ToolMemoryDraft | null) => void;
  submitMemoryDraft: () => Promise<void>;
  registerToolContext: (sessionId: string | null, summary: string | null | undefined) => void;
  consumeToolContext: (sessionId: string | null) => string | null;
  publishToolSnapshot: (payload: { summary?: string; attachments?: ToolAttachment[]; sessionId?: string | null }) => void;
  closeTool: () => void;
};

export const useToolStore = create<ToolStoreState>((set, get) => ({
  isOpen: false,
  entry: null,
  toolContexts: {},
  openFromDecision: (decision, context) => {
    const definition = resolveToolByCallName(decision.tool_call?.name);
    if (!definition) {
      console.warn("[Commander] Unknown tool call", decision.tool_call);
      return;
    }
    set({
      isOpen: true,
      entry: {
        toolId: definition.id,
        params:
          decision.tool_call?.arguments && typeof decision.tool_call.arguments === "object"
            ? (decision.tool_call.arguments as Record<string, unknown>)
            : {},
        paywall: decision.paywall,
        requiresContext: decision.requires_context ?? [],
        decision,
        sessionId: context.sessionId ?? null,
        turnId: context.turnId ?? null,
        assistantMessageId: context.assistantMessageId ?? null,
        memoryDraft: null,
      },
    });
  },
  openTool: (toolId, params = {}) =>
    set({
      isOpen: true,
      entry: {
        toolId,
        params,
        paywall: "free",
        requiresContext: [],
        sessionId: null,
        memoryDraft: null,
      },
    }),
  setMemoryDraft: (draft) =>
    set((state) => {
      if (!state.entry) {
        return state;
      }
      return {
        entry: {
          ...state.entry,
          memoryDraft: draft,
        },
      };
    }),
  submitMemoryDraft: async () => {
    const state = get();
    const entry = state.entry;
    if (!entry || !entry.memoryDraft || !entry.sessionId || !entry.turnId) {
      return;
    }
    const payload: ToolMemoryWritePayload = {
      sessionId: entry.sessionId,
      turnId: entry.turnId,
      toolId: String(entry.memoryDraft.toolId ?? entry.toolId),
      topic: entry.memoryDraft.topic,
      question: entry.memoryDraft.question ?? entry.memoryDraft.topic,
      answer: entry.memoryDraft.answer ?? entry.memoryDraft.topic,
      highlights: entry.memoryDraft.highlights ?? [],
      metadata: entry.memoryDraft.metadata ?? {},
    };
    try {
      await postToolMemoryWrite(payload);
    } catch (error) {
      console.warn("[Commander] Failed to persist LightMem summary", error);
    } finally {
      set((current) => {
        if (!current.entry) {
          return current;
        }
        return {
          entry: {
            ...current.entry,
            memoryDraft: null,
          },
        };
      });
    }
  },
  registerToolContext: (sessionId, summary) =>
    set((state) => {
      const content = typeof summary === "string" ? summary.trim() : "";
      if (!content) {
        return state;
      }
      const key = sessionId ?? "__global__";
      const existing = state.toolContexts[key] ?? [];
      const nextContexts = existing.concat(content).slice(-3);
      return {
        toolContexts: {
          ...state.toolContexts,
          [key]: nextContexts,
        },
      };
    }),
  consumeToolContext: (sessionId) => {
    const key = sessionId ?? "__global__";
    const contexts = get().toolContexts[key];
    if (!contexts || contexts.length === 0) {
      return null;
    }
    set((state) => {
      const next = { ...state.toolContexts };
      delete next[key];
      return { toolContexts: next };
    });
    return contexts.join("\n");
  },
  publishToolSnapshot: ({ summary, attachments, sessionId }) => {
    const targetSession = sessionId ?? get().entry?.sessionId;
    if (!targetSession) {
      return;
    }
    const messageContent = (summary && summary.trim()) || "도구 실행 결과를 반영했습니다.";
    const timestamp = new Date().toISOString();
    const chatStore = useChatStore.getState();
    chatStore.addMessage(targetSession, {
      id: `tool-${nanoid()}`,
      role: "assistant",
      content: messageContent,
      timestamp,
      meta: {
        status: "ready",
        toolAttachments: attachments && attachments.length ? attachments : undefined,
      },
    });
  },
  closeTool: () =>
    set({
      isOpen: false,
      entry: null,
    }),
}));
