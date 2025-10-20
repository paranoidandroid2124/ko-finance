import classNames from "classnames";

type ErrorStateProps = {
  title: string;
  description?: string;
  action?: React.ReactNode;
  className?: string;
};

export function ErrorState({ title, description, action, className }: ErrorStateProps) {
  return (
    <div
      className={classNames(
        "flex flex-col items-center justify-center rounded-xl border border-accent-negative/40 bg-accent-negative/10 px-6 py-10 text-center text-accent-negative dark:border-accent-negative/30 dark:bg-accent-negative/15",
        className
      )}
    >
      <h3 className="text-sm font-semibold">{title}</h3>
      {description && <p className="mt-2 max-w-sm text-xs leading-relaxed text-accent-negative/90">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
