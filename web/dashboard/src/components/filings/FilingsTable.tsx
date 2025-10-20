import classNames from "classnames";

type FilingRow = {
  id: string;
  company: string;
  title: string;
  type: string;
  filedAt: string;
  sentiment: "positive" | "neutral" | "negative";
};

type Props = {
  filings: FilingRow[];
  selectedId?: string;
  onSelect?: (id: string) => void;
};

const sentimentBadge: Record<FilingRow["sentiment"], string> = {
  positive: "bg-accent-positive/15 text-accent-positive",
  neutral: "bg-border-light/60 text-text-secondaryLight dark:bg-border-dark/60 dark:text-text-secondaryDark",
  negative: "bg-accent-negative/15 text-accent-negative"
};

export function FilingsTable({ filings, selectedId, onSelect }: Props) {
  return (
    <div className="rounded-xl border border-border-light bg-background-cardLight shadow-card transition-colors dark:border-border-dark dark:bg-background-cardDark">
      <header className="flex items-center justify-between border-b border-border-light px-4 py-3 text-sm font-semibold dark:border-border-dark">
        <span>최근 공시</span>
        <button className="rounded-md border border-border-light px-3 py-1 text-xs text-text-secondaryLight transition-colors hover:border-primary hover:text-primary dark:border-border-dark dark:text-text-secondaryDark dark:hover:border-primary.dark dark:hover:text-primary.dark">
          필터
        </button>
      </header>
      <div className="max-h-[520px] overflow-y-auto">
        <table className="w-full table-fixed text-sm">
          <thead className="sticky top-0 bg-background-cardLight/90 text-xs uppercase text-text-secondaryLight backdrop-blur dark:bg-background-cardDark/90 dark:text-text-secondaryDark">
            <tr>
              <th className="px-4 py-2 text-left">기업</th>
              <th className="px-4 py-2 text-left">제목</th>
              <th className="px-4 py-2 text-left w-24">유형</th>
              <th className="px-4 py-2 text-left w-28">등록 시각</th>
            </tr>
          </thead>
          <tbody>
            {filings.map((filing) => (
              <tr
                key={filing.id}
                onClick={() => onSelect?.(filing.id)}
                className={classNames(
                  "cursor-pointer border-b border-border-light/70 transition-colors last:border-none hover:bg-primary/5 dark:border-border-dark/70 dark:hover:bg-primary.dark/10",
                  selectedId === filing.id && "bg-primary/10 dark:bg-primary.dark/15"
                )}
              >
                <td className="px-4 py-3 font-medium">{filing.company}</td>
                <td className="px-4 py-3">
                  <p className="line-clamp-1">{filing.title}</p>
                  <span className={`mt-1 inline-flex rounded-full px-2 py-0.5 text-[11px] font-semibold ${sentimentBadge[filing.sentiment]}`}>
                    {filing.sentiment === "positive" ? "긍정" : filing.sentiment === "negative" ? "부정" : "중립"}
                  </span>
                </td>
                <td className="px-4 py-3 text-xs text-text-secondaryLight dark:text-text-secondaryDark">{filing.type}</td>
                <td className="px-4 py-3 text-xs text-text-secondaryLight dark:text-text-secondaryDark">{filing.filedAt}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
