import classNames from "classnames";

type SkeletonBlockProps = {
  lines?: number;
  className?: string;
};

export function SkeletonBlock({ lines = 3, className }: SkeletonBlockProps) {
  return (
    <div
      className={classNames(
        "animate-pulse space-y-3 rounded-xl border border-border-light bg-background-cardLight p-4 dark:border-border-dark dark:bg-background-cardDark",
        className
      )}
    >
      {Array.from({ length: lines }).map((_, index) => (
        <div
          key={index}
          className="h-3 rounded bg-border-light/80 dark:bg-border-dark/60"
          style={{ width: `${85 - index * 10}%` }}
        />
      ))}
    </div>
  );
}
