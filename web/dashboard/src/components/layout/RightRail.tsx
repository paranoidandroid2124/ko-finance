 "use client";

import { useRouter } from "next/navigation";

const alerts = [
  { title: "부정 뉴스 증가", description: "반도체 섹터 감성 -12%p (15분)", tone: "negative" },
  { title: "신규 공시", description: "삼성전자 분기보고서 업로드", tone: "neutral" },
  { title: "RAG self-check", description: "guardrail 경고 1건", tone: "warning" }
];

export function RightRail() {
  const router = useRouter();

  const handleAlertClick = (alertTitle: string) => {
    if (alertTitle.includes("뉴스")) {
      router.push("/news");
    } else if (alertTitle.includes("공시")) {
      router.push("/filings");
    } else {
      router.push("/chat");
    }
  };

  return (
    <aside className="hidden w-80 flex-none space-y-4 rounded-xl border border-border-light bg-background-cardLight px-4 py-5 shadow-card dark:border-border-dark dark:bg-background-cardDark xl:block">
      <section>
        <h2 className="text-sm font-semibold">실시간 알림</h2>
        <ul className="mt-3 space-y-3 text-sm">
          {alerts.map((alert) => (
            <li
              key={alert.title}
              className="rounded-lg border border-border-light/60 bg-white/70 px-3 py-2 transition-colors hover:border-primary hover:text-primary dark:border-border-dark/60 dark:bg-white/5 dark:hover:border-primary.dark"
              role="button"
              tabIndex={0}
              onClick={() => handleAlertClick(alert.title)}
              onKeyDown={(event) => event.key === "Enter" && handleAlertClick(alert.title)}
            >
              <p className="font-medium">{alert.title}</p>
              <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">{alert.description}</p>
            </li>
          ))}
        </ul>
      </section>
      <section>
        <h2 className="text-sm font-semibold">대화형 분석</h2>
        <p className="mt-2 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
          챗봇을 통해 공시·뉴스에 대해 질문하고 근거를 확인하세요.
        </p>
        <button
          onClick={() => router.push("/chat")}
          className="mt-3 w-full rounded-lg bg-primary px-3 py-2 text-sm font-semibold text-white shadow hover:bg-primary-hover"
        >
          새 대화 시작
        </button>
        <div className="mt-3 space-y-2 text-xs">
          <p className="text-text-secondaryLight dark:text-text-secondaryDark">최근 세션</p>
          <div className="rounded-md border border-border-light px-3 py-2 dark:border-border-dark">
            <p className="font-medium text-text-primaryLight dark:text-text-primaryDark">“삼성전자 실적 요약”</p>
            <p className="text-[11px] text-text-secondaryLight dark:text-text-secondaryDark">5분 전</p>
          </div>
        </div>
      </section>
    </aside>
  );
}
