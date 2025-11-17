'use client';

import { create } from 'zustand';
import { nanoid } from 'nanoid';

export type ToastIntent = 'info' | 'success' | 'warning' | 'error';

export type ToastDescriptor = {
  id: string;
  title?: string;
  message: string;
  intent?: ToastIntent;
  duration?: number;
  actionLabel?: string;
  actionHref?: string;
  onAction?: () => void;
};

export type ToastInput = {
  id?: string;
  title?: string;
  message?: string;
  description?: string;
  intent?: ToastIntent;
  duration?: number;
  actionLabel?: string;
  actionHref?: string;
  onAction?: () => void;
};

type ToastStoreState = {
  toasts: ToastDescriptor[];
  show: (toast: ToastInput) => string;
  dismiss: (id: string) => void;
  clear: () => void;
};

export const useToastStore = create<ToastStoreState>((set, _get) => ({
  toasts: [],
  show: (toast) => {
    const id = toast.id ?? nanoid();
    const resolvedMessage = toast.message ?? toast.description ?? toast.title ?? "알림을 표시합니다.";
    const descriptor: ToastDescriptor = {
      id,
      title: toast.title,
      message: resolvedMessage,
      intent: toast.intent ?? 'info',
      duration: toast.duration ?? 5000,
      actionLabel: toast.actionLabel,
      actionHref: toast.actionHref,
      onAction: toast.onAction
    };
    set((state) => ({
      toasts: [...state.toasts.filter((item) => item.id !== id), descriptor]
    }));
    return id;
  },
  dismiss: (id) =>
    set((state) => ({
      toasts: state.toasts.filter((toast) => toast.id !== id)
    })),
  clear: () => set({ toasts: [] })
}));

export const toast = {
  show: (payload: ToastInput) => useToastStore.getState().show(payload),
  dismiss: (id: string) => useToastStore.getState().dismiss(id),
  clear: () => useToastStore.getState().clear()
};
