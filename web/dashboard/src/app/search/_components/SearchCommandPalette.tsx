"use client";

import { useEffect, type MouseEvent } from "react";

export type SearchCommandItem = {
  id: string;
  label: string;
  description?: string;
  shortcut?: string;
  onSelect: () => void;
};

type SearchCommandPaletteProps = {
  open: boolean;
  commands: SearchCommandItem[];
  onClose: () => void;
};

export function SearchCommandPalette({ open, commands, onClose }: SearchCommandPaletteProps) {
  useEffect(() => {
    if (!open) {
      return;
    }
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [open, onClose]);

  if (!open) {
    return null;
  }

  const handleBackdropClick = (event: MouseEvent<HTMLDivElement>) => {
    if (event.target === event.currentTarget) {
      onClose();
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-slate-900/40 p-4 pt-24 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      onClick={handleBackdropClick}
    >
      <div className="w-full max-w-xl overflow-hidden rounded-2xl border border-border-light bg-background-cardLight shadow-2xl dark:border-border-dark dark:bg-background-cardDark">
        <div className="flex items-center justify-between border-b border-border-light/80 px-5 py-3 text-xs font-semibold uppercase tracking-[0.25em] text-text-tertiaryLight dark:border-border-dark dark:text-text-tertiaryDark">
          빠른 명령
          <span className="rounded border border-border-light px-2 py-0.5 text-[11px] text-text-secondaryLight dark:border-border-dark dark:text-text-secondaryDark">
            ESC
          </span>
        </div>
        <ul className="max-h-80 overflow-y-auto p-2">
          {commands.length ? (
            commands.map((command) => (
              <li key={command.id}>
                <button
                  type="button"
                  onClick={() => {
                    command.onSelect();
                    onClose();
                  }}
                  className="flex w-full items-start justify-between gap-4 rounded-xl px-4 py-3 text-left text-sm font-medium text-text-primaryLight transition hover:bg-primary/10 dark:text-text-primaryDark dark:hover:bg-primary.dark/15"
                >
                  <div>
                    <p>{command.label}</p>
                    {command.description ? (
                      <p className="text-xs font-normal text-text-secondaryLight dark:text-text-secondaryDark">
                        {command.description}
                      </p>
                    ) : null}
                  </div>
                  {command.shortcut ? (
                    <span className="rounded border border-border-light px-2 py-0.5 text-[11px] text-text-secondaryLight dark:border-border-dark dark:text-text-secondaryDark">
                      {command.shortcut}
                    </span>
                  ) : null}
                </button>
              </li>
            ))
          ) : (
            <li className="px-4 py-6 text-center text-xs text-text-secondaryLight dark:text-text-secondaryDark">
              실행할 수 있는 명령이 없습니다.
            </li>
          )}
        </ul>
      </div>
    </div>
  );
}
