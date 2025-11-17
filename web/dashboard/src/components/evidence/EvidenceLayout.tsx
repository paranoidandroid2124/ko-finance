import clsx from "classnames";
import type { ReactNode } from "react";

type EvidenceLayoutProps = {
  list: ReactNode;
  detail: ReactNode;
  className?: string;
};

export function EvidenceLayout({ list, detail, className }: EvidenceLayoutProps) {
  return (
    <div
      className={clsx(
        "grid gap-6 lg:grid-cols-[minmax(0,0.45fr)_minmax(0,0.55fr)] xl:grid-cols-[minmax(0,0.4fr)_minmax(0,0.6fr)]",
        className,
      )}
    >
      <div className="flex flex-col gap-4">{list}</div>
      <div className="flex flex-col gap-4">{detail}</div>
    </div>
  );
}
