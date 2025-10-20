export function ChatContextPanel() {
  return (
    <aside className="hidden w-72 flex-none space-y-4 rounded-xl border border-border-light bg-background-cardLight p-4 shadow-card transition-colors dark:border-border-dark dark:bg-background-cardDark lg:block">
      <section>
        <h3 className="text-sm font-semibold">근거 하이라이트</h3>
        <ul className="mt-3 space-y-2 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
          <li className="rounded-lg border border-border-light px-3 py-2 dark:border-border-dark">
            <p className="font-semibold text-text-primaryLight dark:text-text-primaryDark">[삼성전자] 사업보고서 p.12</p>
            <p>“반도체 부문 재고 조정으로 영업이익 감소”</p>
          </li>
          <li className="rounded-lg border border-border-light px-3 py-2 dark:border-border-dark">
            <p className="font-semibold text-text-primaryLight dark:text-text-primaryDark">[뉴스] AI 반도체 수요</p>
            <p>“북미 수요 둔화”</p>
          </li>
        </ul>
      </section>
      <section>
        <h3 className="text-sm font-semibold">Trace & Guardrail</h3>
        <div className="mt-2 space-y-2 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
          <div className="rounded-lg border border-border-light px-3 py-2 dark:border-border-dark">
            <p className="font-semibold text-text-primaryLight dark:text-text-primaryDark">Langfuse Trace</p>
            <p>trace_2025-10-20_09-31</p>
          </div>
          <div className="rounded-lg border border-border-light px-3 py-2 dark:border-border-dark">
            <p className="font-semibold text-text-primaryLight dark:text-text-primaryDark">Guardrail</p>
            <p>위반 없음</p>
          </div>
        </div>
      </section>
    </aside>
  );
}

