import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { PdfHighlightMock, type PdfHighlightRange } from "@/components/chat/PdfHighlightMock";
import { PDF_STRINGS } from "@/i18n/ko";

const mockRanges: PdfHighlightRange[] = [
  {
    id: "hl-1",
    page: 12,
    yStartPct: 30,
    yEndPct: 45,
    summary: "핵심 요약",
    evidenceId: "ev-1"
  },
  {
    id: "hl-2",
    page: 12,
    yStartPct: 60,
    yEndPct: 72,
    summary: "세부 지표",
    evidenceId: "ev-2"
  }
];

describe("PdfHighlightMock", () => {
  it("renders skeletons while loading", () => {
    const { container } = render(
      <PdfHighlightMock
        status="loading"
        documentTitle="테스트 문서"
        pdfUrl="/mock.pdf"
        highlightRanges={[]}
        activeRangeId={undefined}
      />
    );

    expect(screen.getByText(PDF_STRINGS.loading)).toBeInTheDocument();
    expect(container.querySelectorAll(".animate-pulse")).toHaveLength(2);
  });

  it("shows empty placeholder when no highlight exists", () => {
    render(
      <PdfHighlightMock
        status="ready"
        documentTitle="테스트 문서"
        pdfUrl="/mock.pdf"
        highlightRanges={[]}
        activeRangeId={undefined}
      />
    );

    expect(screen.getByText(PDF_STRINGS.empty)).toBeInTheDocument();
  });

  it("renders guardrail message on error", () => {
    render(
      <PdfHighlightMock
        status="error"
        documentTitle="테스트 문서"
        pdfUrl="/mock.pdf"
        highlightRanges={[]}
        activeRangeId={undefined}
      />
    );

    expect(screen.getByText(PDF_STRINGS.error)).toBeInTheDocument();
  });

  it("invokes focus handler when highlight is clicked", () => {
    const focusHandler = vi.fn();
    render(
      <PdfHighlightMock
        status="ready"
        documentTitle="테스트 문서"
        pdfUrl="/mock.pdf"
        highlightRanges={mockRanges}
        activeRangeId="hl-1"
        onFocusHighlight={focusHandler}
      />
    );

    const overlayButton = screen.getAllByRole("button", { name: PDF_STRINGS.overlayLabel })[0];
    fireEvent.click(overlayButton);

    expect(focusHandler).toHaveBeenCalledWith("ev-1");
  });
});
