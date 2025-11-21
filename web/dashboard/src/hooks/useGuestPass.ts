"use client";

import { useCallback, useEffect, useState } from "react";
import { nanoid } from "nanoid";

import { setGuestTokenForRequests } from "@/lib/chatApi";

const STORAGE_KEY = "__nuvien_guest_pass__";

type GuestPassStorage = {
  token: string;
  remaining: number;
  lastUsedAt?: string | null;
};

export type GuestPassState = {
  ready: boolean;
  token: string | null;
  remaining: number;
  isGuest: boolean;
  consume: () => boolean;
  exhaust: () => void;
};

const persistState = (state: GuestPassStorage) => {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    // best-effort persistence; ignore storage errors
  }
};

const loadState = (): GuestPassStorage | null => {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return null;
    }
    const parsed = JSON.parse(raw) as GuestPassStorage;
    if (!parsed?.token) {
      return null;
    }
    return {
      token: parsed.token,
      remaining: typeof parsed.remaining === "number" ? parsed.remaining : 0,
      lastUsedAt: parsed.lastUsedAt ?? null,
    };
  } catch {
    return null;
  }
};

export function useGuestPass(isAuthenticated: boolean): GuestPassState {
  const [ready, setReady] = useState(false);
  const [guestState, setGuestState] = useState<GuestPassStorage | null>(null);

  useEffect(() => {
    if (isAuthenticated) {
      setGuestTokenForRequests(null);
      setGuestState(null);
      setReady(true);
      return;
    }

    if (typeof window === "undefined") {
      return;
    }

    const existing = loadState();
    const nextState: GuestPassStorage =
      existing && existing.token
        ? existing
        : {
            token: `guest_${nanoid(12)}`,
            remaining: 1,
            lastUsedAt: null,
          };

    setGuestState(nextState);
    setGuestTokenForRequests(nextState.token);
    persistState(nextState);
    setReady(true);
  }, [isAuthenticated]);

  const consume = useCallback(() => {
    if (isAuthenticated) {
      return true;
    }
    if (!guestState) {
      return false;
    }
    if (guestState.remaining <= 0) {
      return false;
    }
    const next: GuestPassStorage = {
      ...guestState,
      remaining: guestState.remaining - 1,
      lastUsedAt: new Date().toISOString(),
    };
    setGuestState(next);
    setGuestTokenForRequests(next.token);
    persistState(next);
    return true;
  }, [guestState, isAuthenticated]);

  const exhaust = useCallback(() => {
    if (!guestState || isAuthenticated) {
      return;
    }
    const next: GuestPassStorage = { ...guestState, remaining: 0, lastUsedAt: new Date().toISOString() };
    setGuestState(next);
    setGuestTokenForRequests(next.token);
    persistState(next);
  }, [guestState, isAuthenticated]);

  return {
    ready,
    token: guestState?.token ?? null,
    remaining: isAuthenticated ? Number.POSITIVE_INFINITY : guestState?.remaining ?? 0,
    isGuest: !isAuthenticated,
    consume,
    exhaust,
  };
}

