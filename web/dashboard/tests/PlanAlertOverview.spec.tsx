import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PlanAlertOverview } from "@/components/plan/PlanAlertOverview";
import { proPlanInfo } from "@/testing/fixtures/alerts";

describe("PlanAlertOverview", () => {
  it("renders channel list with friendly labels", () => {
    render(<PlanAlertOverview plan={proPlanInfo} />);

    expect(screen.getByText("플랜에 맞춘 자동화 한도")).toBeInTheDocument();
    expect(screen.getByText("이메일")).toBeInTheDocument();
    expect(screen.getByText("Webhook")).toBeInTheDocument();
  });

  it("shows error message when provided", () => {
    render(<PlanAlertOverview plan={null} error="테스트 에러" />);
    expect(screen.getByText(/알림 플랜 정보를 불러오는 데 잠깐 차질이 생겼어요/)).toBeInTheDocument();
    expect(screen.getByText("테스트 에러")).toBeInTheDocument();
  });
});
