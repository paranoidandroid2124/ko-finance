import { useEvidencePanelStore } from "./EvidencePanelStore";

type EvidenceDiffTabsProps = {
  diffEnabled?: boolean;
  removedCount?: number;
  onToggleDiff?: (nextValue: boolean) => void;
};

export function EvidenceDiffTabs({ diffEnabled, removedCount, onToggleDiff }: EvidenceDiffTabsProps) {
  const diffActive = useEvidencePanelStore((state) => state.diffActive);
  if (!diffEnabled) {
    return null;
  }

  const removedLabel = typeof removedCount === "number" && removedCount > 0 ? `삭제됨 ${removedCount}개` : null;

  return (
    <div className="flex flex-wrap items-center gap-2 text-[11px] text-text-secondaryLight dark:text-text-secondaryDark">
      <button
        type="button"
        className={`rounded-md border px-2 py-1 font-semibold transition-motion-fast ${
          diffActive
            ? "border-primary bg-primary/10 text-primary hover:bg-primary/15"
            : "border-border-light text-text-secondaryLight hover:border-primary/60 hover:text-primary dark:border-border-dark dark:text-text-secondaryDark dark:hover:border-primary"
        }`}
        onClick={() => onToggleDiff?.(!diffActive)}
      >
        변화 살펴보기
      </button>
      {removedLabel ? (
        <span className="rounded-md border border-dashed border-border-light px-2 py-1 font-semibold text-text-secondaryLight dark:border-border-dark dark:text-text-secondaryDark">
          {removedLabel}
        </span>
      ) : null}
    </div>
  );
}
