"use client";

import { useEffect, useRef } from "react";
import type { PageViewport } from "pdfjs-dist/types/src/display/display_utils";

import { useEvidencePanelStore } from "./EvidencePanelStore";
type PdfRect = {
  page: number;
  x: number;
  y: number;
  width: number;
  height: number;
};

export type InlinePdfViewerProps = {
  src: string;
  page?: number | null;
  highlightRect?: PdfRect | null;
  className?: string;
};

export function InlinePdfViewer({ src, page, highlightRect, className }: InlinePdfViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const highlightRef = useRef<HTMLDivElement>(null);
  const viewportRef = useRef<PageViewport | null>(null);
  const [pdfStatus, pdfError, setPdfState] = useEvidencePanelStore((state) => [
    state.pdfStatus,
    state.pdfError,
    state.setPdfState,
  ]);

  const targetPage = Math.max(1, page ?? 1);

  useEffect(() => {
    let cancelled = false;
    let destroyTask: (() => void) | undefined;

    async function renderPdf() {
      if (!src) {
        setPdfState("idle", null);
        return;
      }
      setPdfState("loading", null);

      try {
        const [{ getDocument, GlobalWorkerOptions }, workerModule] = await Promise.all([
          // Use legacy bundle so the browser build does not pull optional canvas dependency.
          import("pdfjs-dist/legacy/build/pdf"),
          import("pdfjs-dist/legacy/build/pdf.worker.js?url"),
        ]);

        if (workerModule?.default) {
          GlobalWorkerOptions.workerSrc = workerModule.default;
        }

        const loadingTask = getDocument({
          url: src,
          withCredentials: src.startsWith("/"),
        });
        destroyTask = () => {
          try {
            loadingTask.destroy();
          } catch {
            // ignored
          }
        };

        const doc = await loadingTask.promise;
        if (cancelled) {
          return;
        }

        const safePage = Math.min(doc.numPages, Math.max(1, targetPage));
        const pdfPage = await doc.getPage(safePage);
        if (cancelled) {
          return;
        }

        const containerWidth = containerRef.current?.clientWidth ?? 0;
        const viewport = pdfPage.getViewport({ scale: 1 });
        const scale = containerWidth ? containerWidth / viewport.width : 1;
        const scaledViewport = pdfPage.getViewport({ scale });

        const canvas = canvasRef.current;
        const context = canvas?.getContext("2d");
        if (!canvas || !context) {
          throw new Error("PDF canvas unavailable.");
        }

        canvas.height = scaledViewport.height;
        canvas.width = scaledViewport.width;
        const renderContext = {
          canvasContext: context,
          viewport: scaledViewport,
        };

        await pdfPage.render(renderContext).promise;
        if (cancelled) {
          return;
        }

        viewportRef.current = scaledViewport;
        applyHighlight();
        setPdfState("ready", null);
      } catch (error) {
        if (cancelled) {
          return;
        }
        const err = error instanceof Error ? error : new Error(String(error));
        setPdfState("error", err.message);
      }
    }

    renderPdf();

    return () => {
      cancelled = true;
      if (typeof destroyTask === "function") {
        destroyTask();
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [src, targetPage, setPdfState]);

  useEffect(() => {
    applyHighlight();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [highlightRect, targetPage, pdfStatus]);

  const applyHighlight = () => {
    if (!highlightRect || highlightRect.page !== targetPage) {
      if (highlightRef.current) {
        highlightRef.current.style.display = "none";
      }
      return;
    }
    const highlight = highlightRef.current;
    if (!highlight) {
      return;
    }

    const viewport = viewportRef.current;
    if (!viewport) {
      highlight.style.display = "none";
      return;
    }

    try {
      const [x1, y1, x2, y2] = viewport.convertToViewportRectangle([
        highlightRect.x,
        highlightRect.y,
        highlightRect.x + highlightRect.width,
        highlightRect.y + highlightRect.height,
      ]);
      const left = Math.min(x1, x2);
      const top = Math.min(y1, y2);
      const width = Math.abs(x2 - x1);
      const height = Math.abs(y2 - y1);
      highlight.style.display = "block";
      highlight.style.left = `${left}px`;
      highlight.style.top = `${top}px`;
      highlight.style.width = `${width}px`;
      highlight.style.height = `${height}px`;
    } catch {
      highlight.style.display = "none";
    }
  };

  return (
    <div ref={containerRef} className={className}>
      <div className="relative overflow-hidden rounded-lg border border-border-light bg-white dark:border-border-dark dark:bg-white/5">
        <canvas ref={canvasRef} className="block w-full" role="img" aria-label="PDF 페이지 미리보기" />
        <div
          ref={highlightRef}
          style={highlightRect ? undefined : { display: "none" }}
          className="pointer-events-none absolute rounded-md border border-primary/60 bg-primary/20 backdrop-blur-[1px]"
        />
        {pdfStatus === "loading" ? (
          <div className="absolute inset-0 flex items-center justify-center bg-white/70 text-xs text-text-secondaryLight dark:bg-background-cardDark/70 dark:text-text-secondaryDark">
            PDF 로딩 중입니다…
          </div>
        ) : null}
        {pdfStatus === "error" ? (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-white/80 p-3 text-center text-xs text-destructive dark:bg-background-cardDark/80">
            <p className="font-semibold">PDF를 불러오지 못했습니다</p>
            {pdfError ? <p className="text-[11px] text-destructive/80">{pdfError}</p> : null}
          </div>
        ) : null}
      </div>
    </div>
  );
}
