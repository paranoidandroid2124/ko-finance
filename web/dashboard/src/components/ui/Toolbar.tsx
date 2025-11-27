import clsx from "clsx";
import type { HTMLAttributes } from "react";

type ToolbarProps = HTMLAttributes<HTMLDivElement>;

/**
 * Toolbar: horizontal control bar with hairline border and glass surface.
 */
export function Toolbar({ className, children, ...props }: ToolbarProps) {
  return (
    <div
      className={clsx(
        "flex items-center gap-2 rounded-2xl border border-border-hair/70 bg-surface-2/80 px-3 py-2 shadow-subtle backdrop-blur-glass",
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
}
