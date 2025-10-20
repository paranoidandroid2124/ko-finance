export function NewsFilterPanel() {
  return (
    <aside className="rounded-xl border border-border-light bg-background-cardLight p-4 shadow-card transition-colors dark:border-border-dark dark:bg-background-cardDark">
      <h3 className="text-sm font-semibold">필터</h3>
      <div className="mt-3 space-y-4 text-sm">
        <section>
          <p className="text-xs font-semibold uppercase text-text-secondaryLight dark:text-text-secondaryDark">섹터</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {["반도체", "바이오", "금융", "에너지"].map((sector) => (
              <button
                key={sector}
                className="rounded-full border border-border-light px-3 py-1 text-xs text-text-secondaryLight transition-colors hover:border-primary hover:text-primary dark:border-border-dark dark:text-text-secondaryDark dark:hover:border-primary.dark dark:hover:text-primary.dark"
              >
                {sector}
              </button>
            ))}
          </div>
        </section>
        <section>
          <p className="text-xs font-semibold uppercase text-text-secondaryLight dark:text-text-secondaryDark">감성 범위</p>
          <div className="mt-2 space-y-2 text-xs">
            <label className="flex items-center justify-between rounded-lg border border-border-light px-3 py-2 dark:border-border-dark">
              <span>부정 강조</span>
              <input type="checkbox" defaultChecked className="accent-primary" />
            </label>
            <label className="flex items-center justify-between rounded-lg border border-border-light px-3 py-2 dark:border-border-dark">
              <span>중립 제외</span>
              <input type="checkbox" className="accent-primary" />
            </label>
          </div>
        </section>
        <section>
          <p className="text-xs font-semibold uppercase text-text-secondaryLight dark:text-text-secondaryDark">기간</p>
          <select className="w-full rounded-lg border border-border-light bg-transparent px-3 py-2 text-sm dark:border-border-dark">
            <option>최근 1시간</option>
            <option>최근 24시간</option>
            <option>최근 7일</option>
          </select>
        </section>
      </div>
    </aside>
  );
}

