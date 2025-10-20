import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { PdfHighlightMock, type PdfHighlightRange } from "@/components/chat/PdfHighlightMock";

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
  // 로딩 상태에서는 스켈레톤 카드가 노출되어 사용자가 진행 상황을 인지할 수 있어야 한다.
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

    expect(screen.getByText("PDF를 준비하는 중입니다.")).toBeInTheDocument();
    expect(container.querySelectorAll(".animate-pulse")).toHaveLength(2);
  });

  // 하이라이트 데이터가 없을 때는 사용자에게 선택을 안내하는 빈 상태 메시지를 제공한다.
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

    expect(
      screen.getByText("선택된 근거에 연결된 하이라이트가 없습니다. 근거 패널에서 다른 항목을 선택해 보세요.")
    ).toBeInTheDocument();
  });

  // 오류 상태에서는 guardrail 메시지를 노출해 사용자가 재시도를 인지하도록 한다.
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

    expect(
      screen.getByText("guardrail이 활성화되었거나 PDF 소스가 준비되지 않았습니다. 잠시 후 다시 시도해주세요.")
    ).toBeInTheDocument();
  });

  // 준비 완료 상태에서는 하이라이트 버튼을 통해 선택 이벤트가 발생해야 한다.
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

    const button = screen.getByRole("button", { name: /세부 지표 하이라이트 선택/i });
    fireEvent.click(button);

    expect(focusHandler).toHaveBeenCalledWith("ev-2");
  });
});
