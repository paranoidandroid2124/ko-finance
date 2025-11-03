"use client";

import clsx from "classnames";

type AdminActorNoteFieldsProps = {
  actor: string;
  note: string;
  onActorChange: (value: string) => void;
  onNoteChange: (value: string) => void;
  actorLabel?: string;
  noteLabel?: string;
  actorPlaceholder?: string;
  notePlaceholder?: string;
  className?: string;
};

export function AdminActorNoteFields({
  actor,
  note,
  onActorChange,
  onNoteChange,
  actorLabel = "실행자(Actor)",
  noteLabel = "변경 메모",
  actorPlaceholder = "운영자 이름",
  notePlaceholder = "예: 업데이트 이유",
  className,
}: AdminActorNoteFieldsProps) {
  return (
    <div className={clsx("grid gap-3 md:grid-cols-2", className)}>
      <label className="flex flex-col gap-1 text-sm text-text-secondaryLight dark:text-text-secondaryDark">
        {actorLabel}
        <input
          type="text"
          value={actor}
          onChange={(event) => onActorChange(event.target.value)}
          placeholder={actorPlaceholder}
          className="rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
        />
      </label>
      <label className="flex flex-col gap-1 text-sm text-text-secondaryLight dark:text-text-secondaryDark">
        {noteLabel}
        <input
          type="text"
          value={note}
          onChange={(event) => onNoteChange(event.target.value)}
          placeholder={notePlaceholder}
          className="rounded-lg border border-border-light bg-background-base px-3 py-2 text-sm text-text-primaryLight focus:border-primary focus:outline-none dark:border-border-dark dark:bg-background-cardDark dark:text-text-primaryDark"
        />
      </label>
    </div>
  );
}

