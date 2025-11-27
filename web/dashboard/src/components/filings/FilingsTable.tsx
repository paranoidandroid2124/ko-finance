import { Download, Loader2 } from "lucide-react";
import classNames from "classnames";
import { type FilingListItem, useFetchFiling } from "@/hooks/useFilings";

type Props = {
  filings: FilingListItem[];
  selectedId?: string;
  onSelect?: (id: string) => void;
};

const sentimentBadge: Record<FilingListItem["sentiment"], string> = {
  positive: "bg-accent-positive/15 text-accent-positive",
  neutral: "bg-border-light/60 text-text-secondaryLight dark:bg-border-dark/60 dark:text-text-secondaryDark",
  negative: "bg-accent-negative/15 text-accent-negative"
};

export function FilingsTable({ filings, selectedId, onSelect }: Props) {
  const fetchFiling = useFetchFiling();

  const handleFetch = (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    fetchFiling.mutate(id);
  };

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
                  <div className="flex flex-col gap-1">
                    <div className="flex items-center gap-2">
                      <p className="line-clamp-1">{filing.title}</p>
                      {filing.status === "PENDING" && (
                        <button
                          onClick={(e) => handleFetch(e, filing.id)}
                          disabled={fetchFiling.isPending}
                          className="flex items-center gap-1 rounded bg-primary/10 px-1.5 py-0.5 text-[10px] font-medium text-primary hover:bg-primary/20 disabled:opacity-50 dark:bg-primary.dark/20 dark:text-primary.dark dark:hover:bg-primary.dark/30"
                          title="원문 가져오기"
                        >
                          {fetchFiling.isPending && fetchFiling.variables === filing.id ? (
                            <Loader2 className="h-3 w-3 animate-spin" />
                          ) : (
                            <Download className="h-3 w-3" />
                          )}
                          <span>Get</span>
                        </button>
                      )}
                    </div>
                    {filing.status === "PENDING" && (
                      <p className="text-[11px] text-text-tertiaryLight dark:text-text-tertiaryDark">
                        원문 미확보 · 가져와야 요약/팩트 표시
                      </p>
                    )}
                    <div className="flex flex-wrap items-center gap-2">
                      <span
                        className={`mt-1 inline-flex rounded-full px-2 py-0.5 text-[11px] font-semibold ${sentimentBadge[filing.sentiment]}`}
                        title={filing.sentimentReason}
                      >
                        {filing.sentiment === "positive" ? "긍정" : filing.sentiment === "negative" ? "부정" : "중립"}
                      </span>
                      {(filing.highlightReason || filing.insightScore !== undefined) && (
                        <span
                          className="mt-1 inline-flex rounded-full bg-primary/10 px-2 py-0.5 text-[11px] font-semibold text-primary"
                          title={
                            filing.highlightReason ||
                            (filing.insightScore !== undefined ? `주목도 ${filing.insightScore?.toFixed(2)}` : undefined)
                          }
                        >
                          주목
                        </span>
                      )}
                    </div>
                    {filing.highlightReason && (
                      <p className="text-[11px] text-text-secondaryLight line-clamp-2 dark:text-text-secondaryDark">
                        {filing.highlightReason}
                      </p>
                    )}
                  </div>
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
