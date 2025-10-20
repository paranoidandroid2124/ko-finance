type ChartPlaceholderProps = {
  title: string;
  subtitle?: string;
  height?: number;
};

export function ChartPlaceholder({ title, subtitle, height = 240 }: ChartPlaceholderProps) {
  return (
    <div className="rounded-xl border border-border-light bg-background-cardLight p-4 shadow-card transition-colors dark:border-border-dark dark:bg-background-cardDark">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold">{title}</h3>
          {subtitle && (
            <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">{subtitle}</p>
          )}
        </div>
        <button className="rounded-md border border-border-light px-2 py-1 text-xs text-text-secondaryLight transition-colors hover:border-primary hover:text-primary dark:border-border-dark dark:text-text-secondaryDark dark:hover:border-primary.dark dark:hover:text-primary.dark">
          기간 선택
        </button>
      </div>
      <div
        className="mt-4 flex items-center justify-center rounded-lg border border-dashed border-border-light/70 text-xs text-text-secondaryLight dark:border-border-dark/70 dark:text-text-secondaryDark"
        style={{ height }}
      >
        차트 영역 – ECharts로 대체 예정
      </div>
    </div>
  );
}

