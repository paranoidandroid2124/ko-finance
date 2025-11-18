"use client";

import { useCallback, useEffect, useMemo } from "react";

import { useIntersectionObserver } from "@/hooks/useIntersectionObserver";

import type { EvidenceItem } from "./types";
import { useEvidencePanelStore } from "./EvidencePanelStore";

type ControllerOptions = {
  items: EvidenceItem[];
  selectedUrnId?: string;
  initialSelectedUrn?: string;
  inlinePdfEnabled: boolean;
  pdfUrl?: string | null;
  diffActiveProp?: boolean;
  onSelectEvidence?: (urnId: string) => void;
  onHoverEvidence?: (urnId: string | undefined) => void;
  onToggleDiff?: (nextValue: boolean) => void;
};

export function useEvidencePanelController({
  items,
  selectedUrnId,
  initialSelectedUrn,
  inlinePdfEnabled,
  pdfUrl,
  diffActiveProp,
  onSelectEvidence,
  onHoverEvidence,
  onToggleDiff,
}: ControllerOptions) {
  const isControlled = selectedUrnId !== undefined;
  const [storeSelection, setStoreSelection] = useEvidencePanelStore((state) => [
    state.selectedUrnId,
    state.setSelectedUrnId,
  ]);
  const [pdfStatus, pdfError, setPdfState] = useEvidencePanelStore((state) => [
    state.pdfStatus,
    state.pdfError,
    state.setPdfState,
  ]);
  const [storeDiffActive, setStoreDiffActive] = useEvidencePanelStore((state) => [
    state.diffActive,
    state.setDiffActive,
  ]);
  const isDiffControlled = diffActiveProp !== undefined;
  const resolvedDiffActive = diffActiveProp ?? storeDiffActive;
  const { observe, unobserve } = useIntersectionObserver({
    rootMargin: "-20% 0px -40% 0px",
  });

  useEffect(() => {
    if (isControlled) {
      setStoreSelection(selectedUrnId);
    } else if (!storeSelection && initialSelectedUrn) {
      setStoreSelection(initialSelectedUrn);
    }
  }, [isControlled, selectedUrnId, initialSelectedUrn, storeSelection, setStoreSelection]);

  const activeUrn = selectedUrnId ?? storeSelection ?? items[0]?.urnId;
  const activeItem = useMemo(
    () => items.find((item) => item.urnId === activeUrn),
    [items, activeUrn],
  );

  const highlightRect = useMemo(() => {
    const rect = activeItem?.anchor?.pdfRect;
    if (!rect) {
      return null;
    }
    return {
      page: rect.page ?? activeItem?.pageNumber ?? 1,
      x: rect.x ?? 0,
      y: rect.y ?? 0,
      width: rect.width ?? 0,
      height: rect.height ?? 0,
    };
  }, [activeItem]);
  const pdfPage = highlightRect?.page ?? activeItem?.pageNumber ?? undefined;

  useEffect(() => {
    if (!inlinePdfEnabled || !pdfUrl || activeItem?.locked) {
      setPdfState("idle", null);
      return;
    }
    setPdfState("loading", null);
  }, [inlinePdfEnabled, pdfUrl, activeItem?.urnId, activeItem?.locked, setPdfState]);

  useEffect(() => {
    if (isDiffControlled) {
      setStoreDiffActive(Boolean(diffActiveProp));
    }
  }, [isDiffControlled, diffActiveProp, setStoreDiffActive]);

  const handleSelect = useCallback(
    (urnId: string) => {
      onSelectEvidence?.(urnId);
      onHoverEvidence?.(undefined);
      if (!isControlled) {
        setStoreSelection(urnId);
      }
    },
    [isControlled, onSelectEvidence, onHoverEvidence, setStoreSelection],
  );

  const bindObserver = useCallback(
    (urnId: string) =>
      (element: HTMLLIElement | null) => {
        if (!element) {
          unobserve(element);
          return;
        }
        observe(element, (entry) => {
          if (!entry.isIntersecting || isControlled) {
            return;
          }
          setStoreSelection((current) => current ?? urnId);
        });
      },
    [observe, unobserve, isControlled, setStoreSelection],
  );

  const handleDiffToggle = useCallback(
    (nextValue: boolean) => {
      if (!isDiffControlled) {
        setStoreDiffActive(nextValue);
      }
      onToggleDiff?.(nextValue);
    },
    [isDiffControlled, onToggleDiff, setStoreDiffActive],
  );

  return {
    activeItem,
    activeUrn,
    pdfStatus,
    pdfError,
    pdfPage,
    highlightRect,
    resolvedDiffActive,
    handleSelect,
    bindObserver,
    handleDiffToggle,
  };
}

export type UseEvidencePanelControllerReturn = ReturnType<typeof useEvidencePanelController>;
