import { useCallback, useEffect, useMemo, useRef } from "react";

export type IntersectionHandler = (entry: IntersectionObserverEntry) => void;

export type UseIntersectionObserverOptions = IntersectionObserverInit & {
  /**
   * When true, stop observing elements after they became visible once.
   */
  freezeOnceVisible?: boolean;
  /**
   * Skip attaching observers in reduced environments (SSR/tests).
   */
  disabled?: boolean;
};

type ObserverMap = Map<Element, IntersectionHandler>;

const defaultOptions: Required<Pick<UseIntersectionObserverOptions, "root" | "rootMargin" | "threshold">> = {
  root: null,
  rootMargin: "0px",
  threshold: 0,
};

const clampThreshold = (value: number) => {
  if (!Number.isFinite(value)) {
    return defaultOptions.threshold;
  }
  return Math.min(1, Math.max(0, value));
};

/**
 * Lightweight wrapper around IntersectionObserver for sharing scroll-sync behaviour.
 */
export function useIntersectionObserver(options: UseIntersectionObserverOptions = {}) {
  const handlersRef = useRef<ObserverMap>(new Map());
  const observerRef = useRef<IntersectionObserver | null>(null);

  const {
    root = defaultOptions.root,
    rootMargin = defaultOptions.rootMargin,
    threshold = defaultOptions.threshold,
    freezeOnceVisible = false,
    disabled = false,
  } = options;

  const normalizedThreshold = useMemo<IntersectionObserverInit["threshold"]>(() => {
    if (Array.isArray(threshold)) {
      const sanitized = threshold.length ? threshold : [defaultOptions.threshold];
      return sanitized.map((value) => clampThreshold(Number(value))) as number[];
    }
    return clampThreshold(Number(threshold ?? defaultOptions.threshold));
  }, [threshold]);

  useEffect(() => {
    if (disabled || typeof window === "undefined" || !("IntersectionObserver" in window)) {
      return () => undefined;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          const handler = handlersRef.current.get(entry.target);
          if (!handler) {
            return;
          }
          handler(entry);
          if (freezeOnceVisible && entry.isIntersecting) {
            observer.unobserve(entry.target);
            handlersRef.current.delete(entry.target);
          }
        });
      },
      { root, rootMargin, threshold: normalizedThreshold },
    );

    observerRef.current = observer;
    handlersRef.current.forEach((_handler, element) => observer.observe(element));

    return () => {
      observer.disconnect();
      observerRef.current = null;
    };
  }, [root, rootMargin, normalizedThreshold, freezeOnceVisible, disabled]);

  const observe = useCallback(
    (element: Element | null, handler: IntersectionHandler) => {
      if (!element || typeof handler !== "function") {
        return;
      }
      handlersRef.current.set(element, handler);
      observerRef.current?.observe(element);
    },
    [],
  );

  const unobserve = useCallback((element: Element | null) => {
    if (!element) {
      return;
    }
    handlersRef.current.delete(element);
    observerRef.current?.unobserve(element);
  }, []);

  const disconnect = useCallback(() => {
    handlersRef.current.clear();
    if (observerRef.current) {
      observerRef.current.disconnect();
      observerRef.current = null;
    }
  }, []);

  useEffect(() => disconnect, [disconnect]);

  return { observe, unobserve, disconnect };
}
