"use client";

type StarterTrialInviteEmailProps = {
  userName?: string;
  activationUrl: string;
};

export function StarterTrialInviteEmail({ userName, activationUrl }: StarterTrialInviteEmailProps) {
  return (
    <table width="100%" cellPadding={0} cellSpacing={0} role="presentation">
      <tbody>
        <tr>
          <td style={{ fontFamily: "Pretendard, Arial, sans-serif", padding: "24px" }}>
            <p style={{ fontSize: "14px", color: "#111" }}>{userName ? `${userName}님,` : "안녕하세요,"}</p>
            <h1 style={{ fontSize: "20px", margin: "12px 0" }}>Starter 30일 체험을 지금 시작해 보세요</h1>
            <p style={{ fontSize: "14px", color: "#333", lineHeight: 1.6 }}>
              워치리스트 50개, 알림 룰 10개, 하루 80회 RAG 질문이 포함된 Starter 체험을 즉시 활성화할 수 있어요. 기간 안에
              해지하시면 비용이 청구되지 않습니다.
            </p>
            <p style={{ margin: "24px 0" }}>
              <a
                href={activationUrl}
                style={{
                  display: "inline-block",
                  padding: "12px 24px",
                  backgroundColor: "#0f172a",
                  color: "#fff",
                  borderRadius: "999px",
                  textDecoration: "none",
                }}
              >
                Starter 체험 시작하기
              </a>
            </p>
            <p style={{ fontSize: "12px", color: "#666" }}>
              링크가 작동하지 않으면 아래 URL을 복사해 브라우저 주소창에 붙여 넣어 주세요.
              <br />
              <span style={{ color: "#0f172a" }}>{activationUrl}</span>
            </p>
          </td>
        </tr>
      </tbody>
    </table>
  );
}
