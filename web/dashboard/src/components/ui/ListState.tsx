import classNames from "classnames";
import type { ReactNode } from "react";

import { SkeletonBlock } from "@/components/ui/SkeletonBlock";
import { EmptyState } from "@/components/ui/EmptyState";

type ListStateProps = {
  state: "loading" | "empty" | "ready";
  className?: string;
  skeletonLines?: number;
  skeleton?: ReactNode;
  emptyTitle?: string;
  emptyDescription?: string;
  emptyAction?: ReactNode;
  emptyIcon?: ReactNode;
  emptyClassName?: string;
  children?: ReactNode;
};

export function ListState({
  state,
  className,
  skeletonLines = 4,
  skeleton,
  emptyTitle = "데이터가 없어요",
  emptyDescription,
  emptyAction,
  emptyIcon,
  emptyClassName,
  children,
}: ListStateProps) {
  if (state === "loading") {
    return (
      <div className={classNames(className)}>
        {skeleton ?? <SkeletonBlock lines={skeletonLines} className="rounded-2xl" />}
      </div>
    );
  }

  if (state === "empty") {
    return (
      <div className={classNames(className)}>
        <EmptyState
          title={emptyTitle}
          description={emptyDescription}
          action={emptyAction}
          icon={emptyIcon}
          className={classNames("border-none bg-transparent px-0 py-6 text-sm", emptyClassName)}
        />
      </div>
    );
  }

  return <div className={classNames(className)}>{children}</div>;
}
