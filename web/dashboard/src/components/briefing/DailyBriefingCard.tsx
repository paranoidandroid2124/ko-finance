import { CalendarClock, MessageCircle, Sparkles } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";

import { useBriefing } from "@/hooks/useBriefing";
import { formatDateTime } from "@/lib/date";
import { cn } from "@/lib/utils";

type Props = {
  className?: string;
};

export function DailyBriefingCard({ className }: Props) {
  const { data, isLoading, isError } = useBriefing();

  if (isError) return null;

  const items = data?.items ?? [];
  const generatedAt = data?.generatedAt ? formatDateTime(data.generatedAt) : "오늘 생성";

  const prefillHref = (itemTitle: string, itemSummary?: string | null) => ({
    pathname: "/dashboard" as Route,
    query: {
      prefill: itemSummary ? `${itemTitle}\n${itemSummary}` : itemTitle
    }
  });

  return (
    <div
      className={cn(
        "w-full max-w-xl rounded-2xl border border-border-light bg-background-card/80 p-4 shadow-lg backdrop-blur-md dark:border-border-dark dark:bg-background-cardDark/80",
        className
      )}
    >
      <div className="flex items-center gap-2 text-sm font-semibold text-primary">
        <Sparkles className="h-4 w-4" aria-hidden />
        <span>프로액티브 인사이트</span>
      </div>
      <div className="mt-1 flex items-center gap-2 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
        <CalendarClock className="h-4 w-4" aria-hidden />
        <span>{generatedAt}</span>
      </div>

      {isLoading ? (
        <div className="mt-4 space-y-2">
          <div className="h-3 w-3/4 animate-pulse rounded bg-border-subtle" />
          <div className="h-3 w-5/6 animate-pulse rounded bg-border-subtle" />
        </div>
      ) : items.length === 0 ? (
        <p className="mt-4 text-sm text-text-secondaryLight dark:text-text-secondaryDark">
          아직 브리핑이 생성되지 않았습니다. 잠시 후 다시 확인해 주세요.
        </p>
      ) : (
        <ul className="mt-4 space-y-3">
          {items.map((item, index) => (
            <li
              key={`${item.title}-${index}`}
              className="rounded-xl border border-border-subtle bg-background-base/60 p-3 dark:border-border-dark dark:bg-background-baseDark/60"
            >
              <p className="text-sm font-semibold text-text-primaryLight dark:text-text-primaryDark">{item.title}</p>
              {item.summary ? (
                <p className="mt-1 line-clamp-3 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                  {item.summary}
                </p>
              ) : null}
              <div className="mt-2 flex flex-wrap gap-2 text-xs text-text-secondaryLight dark:text-text-secondaryDark">
                {item.ticker ? <span className="rounded-full bg-border-subtle px-2 py-1">{item.ticker}</span> : null}
                {item.targetUrl ? (
                  <Link
                    href={item.targetUrl as Route}
                    className="underline underline-offset-4 hover:text-primary dark:hover:text-primary.dark"
                  >
                    상세 보기
                  </Link>
                ) : null}
              </div>
              <div className="mt-3 flex justify-end">
                <Link
                  href={prefillHref(item.title, item.summary)}
                  className="inline-flex items-center gap-2 rounded-full bg-primary px-3 py-1.5 text-xs font-semibold text-white shadow-md transition hover:shadow-lg"
                >
                  <MessageCircle className="h-3.5 w-3.5" aria-hidden />
                  채팅으로 이어보기
                </Link>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
