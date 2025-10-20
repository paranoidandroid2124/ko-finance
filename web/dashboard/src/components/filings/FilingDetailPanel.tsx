"use client";

import { useRouter } from "next/navigation";
import { useCallback } from "react";
import { useChatStore } from "@/store/chatStore";

type FilingDetail = {
  id: string;
  company: string;
  title: string;
  type: string;
  filedAt: string;
  summary: string;
  facts: { label: string; value: string; anchor?: string }[];
  pdfUrl?: string;
  sentiment: "positive" | "neutral" | "negative";
};

const sentimentText: Record<FilingDetail["sentiment"], { label: string; description: string }> = {
  positive: { label: "긍정", description: "긍정적 시그널이 감지되었습니다." },
  neutral: { label: "중립", description: "중립적이거나 유의미한 변화가 없습니다." },
  negative: { label: "부정", description: "주의가 필요한 부정적 신호가 감지되었습니다." }
};

export function FilingDetailPanel({ filing }: { filing: FilingDetail }) {
  const sentiment = sentimentText[filing.sentiment];
  const router = useRouter();
  const startFilingConversation = useChatStore((state) => state.startFilingConversation);

  const handleAskClick = useCallback(() => {
    if (!filing.summary?.trim()) {
      window.alert("요약이 없어 챗 세션을 시작할 수 없습니다.");
      return;
    }

    const sessionId = startFilingConversation({
      filingId: filing.id,
      company: filing.company,
      title: filing.title,
      summary: filing.summary
    });

    router.push(`/chat?session=${sessionId}`);
  }, [filing, router, startFilingConversation]);

  return (
    <aside className="flex h-full flex-col rounded-xl border border-border-light bg-background-cardLight p-5 shadow-card transition-colors dark:border-border-dark dark:bg-background-cardDark">
      <header>
        <p className="text-xs font-semibold uppercase text-text-secondaryLight dark:text-text-secondaryDark">선택된 공시</p>
        <h2 className="mt-2 text-lg font-semibold">{filing.company}</h2>
        <p className="text-sm text-text-secondaryLight dark:text-text-secondaryDark">{filing.title}</p>
        <div className="mt-3 flex items-center gap-2 text-xs">
          <span className="rounded-full border border-border-light px-2 py-0.5 dark:border-border-dark">{filing.type}</span>
          <span className="text-text-secondaryLight dark:text-text-secondaryDark">{filing.filedAt}</span>
        </div>
        <div className="mt-4 rounded-lg border border-border-light bg-white/70 p-3 text-xs dark:border-border-dark dark:bg-white/5">
          <p className="font-semibold">{sentiment.label}</p>
          <p className="mt-1 text-text-secondaryLight dark:text-text-secondaryDark">{sentiment.description}</p>
        </div>
      </header>

      <section className="mt-5 space-y-4 text-sm">
        <div>
          <h3 className="text-sm font-semibold">요약</h3>
          <p className="mt-2 text-text-secondaryLight dark:text-text-secondaryDark">{filing.summary}</p>
        </div>

        <div>
          <h3 className="text-sm font-semibold">추출 팩트</h3>
          <ul className="mt-2 space-y-2 text-sm">
            {filing.facts.map((fact) => (
              <li key={fact.label} className="rounded-lg border border-border-light px-3 py-2 text-xs dark:border-border-dark">
                <p className="font-semibold text-text-primaryLight dark:text-text-primaryDark">{fact.label}</p>
                <p className="text-text-secondaryLight dark:text-text-secondaryDark">
                  {fact.value}
                  {fact.anchor && <span className="ml-2 text-[11px] text-primary">({fact.anchor})</span>}
                </p>
              </li>
            ))}
          </ul>
        </div>
      </section>

      <footer className="mt-auto">
        <div className="rounded-lg border border-dashed border-border-light p-3 text-xs text-text-secondaryLight dark:border-border-dark dark:text-text-secondaryDark">
          <p>PDF 하이라이트는 곧 연결될 예정입니다.</p>
        </div>
        <div className="mt-3 flex gap-2">
          <button className="flex-1 rounded-lg bg-primary px-3 py-2 text-sm font-semibold text-white shadow hover:bg-primary-hover">
            PDF 열기
          </button>
          <button
            onClick={handleAskClick}
            className="flex-1 rounded-lg border border-border-light px-3 py-2 text-sm font-semibold text-text-secondaryLight transition-colors hover:border-primary hover:text-primary dark:border-border-dark dark:text-text-secondaryDark dark:hover:border-primary.dark dark:hover:text-primary.dark"
          >
            질문하기
          </button>
        </div>
      </footer>
    </aside>
  );
}

