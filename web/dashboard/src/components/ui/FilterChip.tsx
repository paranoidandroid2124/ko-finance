import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from "react";
import clsx from "clsx";

type FilterChipProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  active?: boolean;
  icon?: ReactNode;
};

export const FilterChip = forwardRef<HTMLButtonElement, FilterChipProps>(function FilterChip(
  { active = false, icon, className, children, ...props },
  ref,
) {
  return (
    <button
      ref={ref}
      type="button"
      className={clsx(
        "inline-flex items-center gap-1 rounded-full border px-3 py-1.5 text-sm font-medium transition-all duration-150 ease-out focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-1",
        active
          ? "border-primary/80 bg-primary/15 text-primary shadow-sm hover:bg-primary/20 focus-visible:ring-primary/50 dark:border-primary.dark/80 dark:bg-primary.dark/20 dark:text-primary.dark dark:hover:bg-primary.dark/25"
          : "border-border-light bg-background-light text-text-secondaryLight hover:border-primary/40 hover:text-primary focus-visible:ring-primary/40 dark:border-border-dark dark:bg-background-dark dark:text-text-secondaryDark dark:hover:border-primary.dark/40 dark:hover:text-primary.dark",
        className,
      )}
      aria-pressed={active}
      {...props}
    >
      {icon ? <span className="flex h-4 w-4 items-center justify-center">{icon}</span> : null}
      <span className="whitespace-nowrap">{children}</span>
    </button>
  );
});
