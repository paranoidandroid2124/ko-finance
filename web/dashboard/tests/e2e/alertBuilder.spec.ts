import { test, expect } from "@playwright/test";

test.describe("Alerts Builder plan flows", () => {
  test("Free 플랜 사용자는 업그레이드 모달을 안내받는다", async ({ page }) => {
    test.fixme(true, "Playwright 환경에서 Free 플랜 시드가 준비되면 구현 예정");

    await test.step("플랜이 Free인 계정으로 대시보드 진입", async () => {
      await page.goto("/alerts/builder?plan=free");
    });

    await test.step("잠금 안내와 CTA 확인", async () => {
      const lockCard = page.locator("[data-testid='plan-lock']");
      await expect(lockCard).toBeVisible();
      await expect(lockCard).toContainText("Pro");
      await expect(lockCard).toContainText("업그레이드");
    });
  });

  test("Pro 플랜 사용자는 Slack 채널 추가 후 제출할 수 있다", async ({ page }) => {
    test.fixme(true, "백엔드 모킹 및 시드 데이터 연결 필요");

    await test.step("Pro 플랜 계정으로 알림 빌더 로드", async () => {
      await page.goto("/alerts/builder?plan=pro");
    });

    await test.step("필수 필드를 채우고 Slack 채널을 활성화", async () => {
      await page.getByPlaceholder(/TEST/).fill("분기 보고서 알람");
      await page.getByPlaceholder(/KOSPI:/).fill("KOFC");
      await page.getByRole("checkbox", { name: /slack/i }).check();
      await page.getByPlaceholder(/hooks\.slack\.com/i).fill("https://hooks.slack.com/services/demo");
    });

    await test.step("제출 후 성공 알림을 확인", async () => {
      await page.getByRole("button", { name: /저장/ }).click();
      await expect(page.getByText("알림이 준비됐어요")).toBeVisible();
    });
  });

  test("Enterprise 플랜은 PagerDuty 검증 오류를 표기한다", async ({ page }) => {
    test.fixme(true, "Playwright용 Mock 서버 준비 필요");

    await test.step("Enterprise 플랜으로 빌더를 연다", async () => {
      await page.goto("/alerts/builder?plan=enterprise");
    });

    await test.step("PagerDuty 채널을 켜고 잘못된 키를 입력한다", async () => {
      await page.getByRole("checkbox", { name: /pagerduty/i }).check();
      await page.getByPlaceholder(/Routing Key/).fill("short-key");
      await page.getByRole("button", { name: /저장/ }).click();
    });

    await test.step("검증 오류와 포커스를 확인", async () => {
      const errorMessage = page.getByText(/Routing Key/);
      await expect(errorMessage).toBeVisible();
      await expect(page.getByPlaceholder(/Routing Key/)).toBeFocused();
    });
  });
});
