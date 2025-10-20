import { TrendingDown, TrendingUp } from "lucide-react";

type Trend = "up" | "down" | "flat";

export type KpiCardProps = {
  title: string;
  value: string;
  delta: string;
  trend?: Trend;
  description?: string;
};

export function KpiCard({ title, value, delta, trend = "flat", description }: KpiCardProps) {
  const trendIcon =
    trend === "up" ? (
      <TrendingUp className="h-4 w-4 text-accent-positive" />
    ) : trend === "down" ? (
      <TrendingDown className="h-4 w-4 text-accent-negative" />
    ) : null;

  const deltaColor =
    trend === "up"
      ? "text-accent-positive"
      : trend === "down"
        ? "text-accent-negative"
        : "text-text-secondaryLight dark:text-text-secondaryDark";

  return (
    <div className="flex flex-col justify-between rounded-xl border border-border-light bg-background-cardLight p-4 shadow-card transition-colors dark:border-border-dark dark:bg-background-cardDark">
      <div className="text-xs font-medium uppercase tracking-wide text-text-secondaryLight dark:text-text-secondaryDark">
        {title}
      </div>
      <div className="mt-3 flex items-end justify-between">
        <div>
          <p className="text-2xl font-semibold">{value}</p>
          <div className={`mt-1 flex items-center gap-1 text-xs font-semibold ${deltaColor}`}>
            {trendIcon}
            <span>{delta}</span>
          </div>
        </div>
        <div className="h-12 w-20 rounded-md bg-gradient-to-tr from-primary/20 to-primary/5 dark:from-primary.dark/25 dark:to-primary.dark/10" />
      </div>
      {description && (
        <p className="mt-3 text-xs text-text-secondaryLight dark:text-text-secondaryDark">{description}</p>
      )}
    </div>
  );
}

