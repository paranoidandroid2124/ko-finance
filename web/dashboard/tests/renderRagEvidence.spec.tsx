import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { RagEvidencePanel } from "@/components/chat/RenderRagEvidence";
import type { RagEvidenceItem } from "@/store/chatStore";

const mockItems: RagEvidenceItem[] = [
  {
    id: "ev-1",
    title: "재무 분석",
    snippet: "재무 지표 변동을 요약한 문단입니다.",
    page: 10,
    score: 0.8
  },
  {
    id: "ev-2",
    title: "시장 전망",
    snippet: "시장 환경과 위험 요소를 설명합니다.",
    page: 17,
    score: 0.6
  }
];

describe("RagEvidencePanel", () => {
  // 로딩 상태일 때 스켈레톤과 안내 텍스트가 노출되는지 확인한다.
  it("renders loading skeleton when status is loading", () => {
    const { container } = render(
      <RagEvidencePanel status="loading" items={[]} confidence={0.5} activeId={undefined} errorMessage={undefined} />
    );

    expect(screen.getByText("RAG 근거를 불러오는 중입니다.")).toBeInTheDocument();
    expect(container.querySelectorAll(".animate-pulse")).toHaveLength(3);
  });

  // 근거가 비어있을 때 빈 상태 메시지를 제공하여 UX 공백을 방지한다.
  it("shows empty placeholder when no items are available", () => {
    render(<RagEvidencePanel status="ready" items={[]} confidence={undefined} activeId={undefined} />);

    expect(screen.getByText("질문을 전송하면 연관된 근거가 여기에 표시됩니다.")).toBeInTheDocument();
  });

  // 오류 발생 시 guardrail 메시지를 노출해 사용자가 대응할 수 있도록 한다.
  it("displays error message when status is error", () => {
    render(
      <RagEvidencePanel
        status="error"
        items={[]}
        confidence={undefined}
        activeId={undefined}
        errorMessage="임시 guardrail 경고"
      />
    );

    expect(screen.getByText("임시 guardrail 경고")).toBeInTheDocument();
    expect(screen.getByText("guardrail이 활성화되었거나 네트워크 문제가 발생했습니다. 다시 시도해주세요.")).toBeInTheDocument();
  });

  // 근거가 있을 때 선택/신뢰도 정보가 정확하게 반영되는지 검증한다.
  it("renders evidence items and handles selection trigger", () => {
    const handleSelect = vi.fn();
    render(
      <RagEvidencePanel
        status="ready"
        items={mockItems}
        confidence={0.73}
        activeId="ev-1"
        onSelectItem={handleSelect}
      />
    );

    expect(screen.getByText("73% 신뢰도")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /재무 분석/i })).toHaveAttribute("aria-pressed", "true");

    fireEvent.click(screen.getByRole("button", { name: /시장 전망/i }));
    expect(handleSelect).toHaveBeenCalledWith("ev-2");
  });
});
