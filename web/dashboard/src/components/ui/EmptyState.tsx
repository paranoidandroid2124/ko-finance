import classNames from "classnames";

type EmptyStateProps = {
  title: string;
  description?: string;
  action?: React.ReactNode;
  icon?: React.ReactNode;
  className?: string;
};

export function EmptyState({ title, description, action, icon, className }: EmptyStateProps) {
  return (
    <div
      className={classNames(
        "flex flex-col items-center justify-center rounded-xl border border-dashed border-border-light bg-background-cardLight px-6 py-10 text-center dark:border-border-dark dark:bg-background-cardDark",
        className
      )}
    >
      {icon && <div className="mb-3 text-3xl text-primary">{icon}</div>}
      <h3 className="text-sm font-semibold text-text-primaryLight dark:text-text-primaryDark">{title}</h3>
      {description && (
        <p className="mt-2 max-w-sm text-xs leading-relaxed text-text-secondaryLight dark:text-text-secondaryDark">{description}</p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
