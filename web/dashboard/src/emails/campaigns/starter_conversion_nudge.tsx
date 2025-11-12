"use client";

type StarterConversionNudgeEmailProps = {
  userName?: string;
  upgradeUrl: string;
  daysLeft: number;
};

export function StarterConversionNudgeEmail({ userName, upgradeUrl, daysLeft }: StarterConversionNudgeEmailProps) {
  return (
    <table width="100%" cellPadding={0} cellSpacing={0} role="presentation">
      <tbody>
        <tr>
          <td style={{ fontFamily: "Pretendard, Arial, sans-serif", padding: "24px" }}>
            <p style={{ fontSize: "14px", color: "#111" }}>
              {userName ? `${userName}님,` : "안녕하세요,"} Starter 체험이 {daysLeft}일 후 종료됩니다.
            </p>
            <h1 style={{ fontSize: "20px", margin: "12px 0" }}>자동화 흐름을 끊김 없이 이어가세요</h1>
            <p style={{ fontSize: "14px", color: "#333", lineHeight: 1.6 }}>
              지금 업그레이드하면 알림 룰과 PDF 하이라이트, 워치리스트 자동화를 그대로 유지할 수 있어요. 체험 종료 후에는
              Free 플랜 한도로 전환됩니다.
            </p>
            <ul style={{ fontSize: "13px", color: "#333", lineHeight: 1.6, paddingLeft: "20px" }}>
              <li>워치리스트 50개와 알림 룰 10개 유지</li>
              <li>하루 80회 RAG 질문과 PDF 근거 스니펫</li>
              <li>Starter 30일 Pro 체험 쿠폰 포함</li>
            </ul>
            <p style={{ margin: "24px 0" }}>
              <a
                href={upgradeUrl}
                style={{
                  display: "inline-block",
                  padding: "12px 24px",
                  backgroundColor: "#0ea5e9",
                  color: "#fff",
                  borderRadius: "999px",
                  textDecoration: "none",
                }}
              >
                Starter 업그레이드
              </a>
            </p>
            <p style={{ fontSize: "12px", color: "#666" }}>
              링크가 열리지 않으면 아래 URL을 복사해 브라우저 주소창에 붙여 넣어 주세요.
              <br />
              <span style={{ color: "#0f172a" }}>{upgradeUrl}</span>
            </p>
          </td>
        </tr>
      </tbody>
    </table>
  );
}
