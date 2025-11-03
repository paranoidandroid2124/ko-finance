"use client";

import { useEffect, useMemo, useRef, useState } from "react";

import { resolveApiBase } from "@/lib/apiBase";
import type { RagEvidenceItem } from "@/store/chatStore";

type XmlDocument = {
  name: string;
  path: string;
  content: string;
};

type FilingXmlViewerProps = {
  filingId?: string;
  evidenceItems: RagEvidenceItem[];
  activeEvidenceId?: string;
};

const HIGHLIGHT_CLASS = "xml-highlight-active";

const isNonEmptyString = (value: unknown): value is string =>
  typeof value === "string" && value.trim().length > 0;

const deriveCandidatePath = (metadata: Record<string, unknown>): string | null => {
  const candidates = [
    metadata.path,
    metadata.file_path,
    metadata.filePath,
    metadata.source_path,
    metadata.sourcePath
  ];
  for (const candidate of candidates) {
    if (isNonEmptyString(candidate)) {
      return candidate.trim();
    }
  }
  return null;
};

export function FilingXmlViewer({ filingId, evidenceItems, activeEvidenceId }: FilingXmlViewerProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const [documents, setDocuments] = useState<XmlDocument[]>([]);
  const [activeDocIndex, setActiveDocIndex] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const evidenceById = useMemo(() => {
    const map = new Map<string, RagEvidenceItem>();
    evidenceItems.forEach((item) => map.set(item.id, item));
    return map;
  }, [evidenceItems]);

  const activeEvidence = activeEvidenceId ? evidenceById.get(activeEvidenceId) : undefined;

  useEffect(() => {
    if (!filingId) {
      setDocuments([]);
      setActiveDocIndex(0);
      setErrorMessage(null);
      return;
    }

    let cancelled = false;
    const fetchXmlDocuments = async () => {
      try {
        setIsLoading(true);
        setErrorMessage(null);
        const response = await fetch(`${resolveApiBase()}/api/v1/filings/${filingId}/xml`);
        if (!response.ok) {
          const detail = await response.text();
          throw new Error(detail || `XML 문서 요청이 실패했습니다 (status ${response.status}).`);
        }
        const payload = await response.json();
        if (!payload?.documents?.length) {
          throw new Error("연결된 XML 문서를 찾지 못했습니다.");
        }
        if (!cancelled) {
          setDocuments(
            payload.documents.map((doc: XmlDocument) => ({
              name: doc.name,
              path: doc.path,
              content: doc.content
            }))
          );
          setActiveDocIndex(0);
        }
      } catch (err) {
        console.error("Failed to fetch XML documents", err);
        if (!cancelled) {
          setDocuments([]);
          setActiveDocIndex(0);
          setErrorMessage(err instanceof Error ? err.message : "XML 문서를 불러오지 못했습니다.");
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    };

    fetchXmlDocuments();

    return () => {
      cancelled = true;
    };
  }, [filingId]);

  useEffect(() => {
    if (!documents.length || !activeEvidence) {
      return;
    }
    const metadata = (activeEvidence.metadata ?? {}) as Record<string, unknown>;
    const preferredPath = deriveCandidatePath(metadata);
    if (!preferredPath) {
      return;
    }
    const nextIndex = documents.findIndex(
      (doc) => doc.path === preferredPath || doc.name === preferredPath
    );
    if (nextIndex >= 0 && nextIndex !== activeDocIndex) {
      setActiveDocIndex(nextIndex);
    }
  }, [documents, activeEvidence, activeDocIndex]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) {
      return;
    }
    const doc = documents[activeDocIndex];
    if (!doc) {
      container.innerHTML = "";
      return;
    }
    const parser = new DOMParser();
    const xmlDoc = parser.parseFromString(doc.content, "text/xml");
    const serializer = new XMLSerializer();
    const html = serializer.serializeToString(xmlDoc);
    container.innerHTML = html;
    container.scrollTop = 0;
  }, [documents, activeDocIndex]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) {
      return;
    }
    container.querySelectorAll(`.${HIGHLIGHT_CLASS}`).forEach((element) => {
      element.classList.remove(HIGHLIGHT_CLASS);
    });

    if (!activeEvidence) {
      return;
    }

    const metadata = (activeEvidence.metadata ?? {}) as Record<string, unknown>;
    const xpathRaw = isNonEmptyString(metadata.xpath) ? metadata.xpath : null;
    if (!xpathRaw) {
      return;
    }

    const expression = xpathRaw.startsWith("/") ? `.${xpathRaw}` : `./${xpathRaw}`;
    try {
      const result = document.evaluate(
        expression,
        container,
        null,
        XPathResult.FIRST_ORDERED_NODE_TYPE,
        null
      );
      const target = result.singleNodeValue as HTMLElement | null;
      if (!target) {
        return;
      }
      target.classList.add(HIGHLIGHT_CLASS);
      target.scrollIntoView({ block: "center", behavior: "smooth" });
    } catch (err) {
      console.warn("Failed to evaluate XPath", expression, err);
    }
  }, [activeEvidence, documents, activeDocIndex]);

  if (!filingId) {
    return (
      <section className="rounded-xl border border-border-light bg-white/70 p-3 text-xs text-text-secondaryLight dark:border-border-dark dark:bg-white/5 dark:text-text-secondaryDark">
        연결된 공시 ID가 없어 XML을 표시할 수 없습니다.
      </section>
    );
  }

  if (isLoading) {
    return (
      <section className="rounded-xl border border-border-light bg-white/70 p-3 text-xs text-text-secondaryLight dark:border-border-dark dark:bg-white/5 dark:text-text-secondaryDark">
        XML 문서를 불러오는 중입니다…
      </section>
    );
  }

  if (errorMessage) {
    return (
      <section className="rounded-xl border border-destructive/40 bg-destructive/5 p-3 text-xs text-destructive dark:border-destructive/50 dark:bg-destructive/10">
        {errorMessage}
      </section>
    );
  }

  if (!documents.length) {
    return (
      <section className="rounded-xl border border-dashed border-border-light bg-white/70 p-3 text-xs text-text-secondaryLight dark:border-border-dark dark:bg-white/5 dark:text-text-secondaryDark">
        표시할 XML 문서가 없습니다.
      </section>
    );
  }

  const activeDocument = documents[activeDocIndex];

  return (
    <section className="space-y-3 rounded-xl border border-border-light bg-white/70 p-3 text-xs shadow-sm transition-colors dark:border-border-dark dark:bg-white/5">
      <header className="flex items-center justify-between gap-3">
        <div>
          <p className="text-[11px] font-semibold uppercase text-primary">XML 원문</p>
          <p className="text-[11px] text-text-secondaryLight dark:text-text-secondaryDark">
            RAG 근거가 지목한 XML 위치를 강조 표시합니다.
          </p>
        </div>
        {documents.length > 1 ? (
          <div className="flex gap-2">
            {documents.map((doc, index) => (
              <button
                key={doc.path}
                type="button"
                onClick={() => setActiveDocIndex(index)}
                className={`rounded-md border px-2 py-1 text-[11px] font-medium transition-colors ${
                  index === activeDocIndex
                    ? "border-primary bg-primary/10 text-primary"
                    : "border-border-light text-text-secondaryLight hover:border-primary hover:text-primary dark:border-border-dark dark:text-text-secondaryDark dark:hover:border-primary.dark dark:hover:text-primary.dark"
                }`}
              >
                {doc.name}
              </button>
            ))}
          </div>
        ) : null}
      </header>

      {activeDocument ? (
        <div className="rounded-lg border border-border-light bg-background-cardLight/60 p-2 dark:border-border-dark dark:bg-background-cardDark/60">
          <div
            ref={containerRef}
            className="xml-viewer-container h-80 overflow-auto whitespace-pre-wrap break-words text-[11px] text-text-secondaryLight dark:text-text-secondaryDark"
          />
        </div>
      ) : null}

      <style jsx global>{`
        .xml-viewer-container {
          font-family: ui-monospace, SFMono-Regular, SFMono, Menlo, Monaco, Consolas, 'Liberation Mono',
            'Courier New', monospace;
        }
        .xml-viewer-container .${HIGHLIGHT_CLASS} {
          background-color: rgba(59, 130, 246, 0.25);
          outline: 1px solid rgba(59, 130, 246, 0.6);
          border-radius: 4px;
        }
      `}</style>
    </section>
  );
}
