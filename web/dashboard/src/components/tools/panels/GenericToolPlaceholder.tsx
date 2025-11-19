"use client";

type GenericToolPlaceholderProps = {
  title: string;
  description: string;
  hint?: string;
  children?: React.ReactNode;
};

export function GenericToolPlaceholder({ title, description, hint, children }: GenericToolPlaceholderProps) {
  return (
    <div className="flex h-full flex-col gap-4 rounded-2xl border border-dashed border-border-light bg-background-cardLight p-6 text-text-secondaryLight dark:border-border-dark dark:bg-background-cardDark dark:text-text-secondaryDark">
      <div>
        <p className="text-sm font-semibold uppercase tracking-wide text-primary dark:text-primary.dark">{title}</p>
        <p className="mt-1 text-sm">{description}</p>
      </div>
      {hint ? <p className="rounded-xl bg-background px-4 py-2 text-xs text-text-secondaryLight dark:bg-background-dark dark:text-text-secondaryDark">{hint}</p> : null}
      {children}
    </div>
  );
}
