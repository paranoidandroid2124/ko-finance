import type { ReactNode } from "react";
import Link from "next/link";
import classNames from "classnames";

export type LegalSectionContent =
  | { type: "paragraph"; text: string }
  | { type: "list"; title?: string; items: string[] }
  | { type: "note"; text: string }
  | { type: "link"; label: string; href: string };

export type LegalSection = {
  id: string;
  title: string;
  description?: string;
  contents: LegalSectionContent[];
};

type LegalDocumentPageProps = {
  title: string;
  subtitle?: string;
  updatedAtLabel: string;
  sections: LegalSection[];
};

function renderContent(content: LegalSectionContent, index: number): ReactNode {
  if (content.type === "paragraph" || content.type === "note") {
    return (
      <p
        key={index}
        className={classNames(
          "text-sm leading-relaxed text-text-secondaryLight dark:text-text-secondaryDark",
          content.type === "note" ? "rounded-lg bg-border-light/30 px-3 py-2 dark:bg-border-dark/30" : undefined,
        )}
      >
        {content.text}
      </p>
    );
  }
  if (content.type === "list") {
    return (
      <div key={index} className="text-sm">
        {content.title ? (
          <p className="font-semibold text-text-primaryLight dark:text-text-primaryDark">{content.title}</p>
        ) : null}
        <ul className="mt-2 list-disc space-y-1 pl-5 text-text-secondaryLight dark:text-text-secondaryDark">
          {content.items.map((item, idx) => (
            <li key={idx}>{item}</li>
          ))}
        </ul>
      </div>
    );
  }
  if (content.type === "link") {
    return (
      <Link
        key={index}
        href={content.href}
        className="text-sm font-semibold text-primary hover:underline dark:text-primary.dark"
      >
        {content.label}
      </Link>
    );
  }
  return null;
}

export function LegalDocumentPage({ title, subtitle, updatedAtLabel, sections }: LegalDocumentPageProps) {
  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-10 px-4 py-12 sm:px-6 lg:px-8">
      <header className="space-y-4">
        <p className="text-xs uppercase tracking-[0.2em] text-primary/80 dark:text-primary.dark/80">Legal Notice</p>
        <h1 className="text-3xl font-semibold text-text-primaryLight dark:text-text-primaryDark">{title}</h1>
        {subtitle ? (
          <p className="text-base leading-relaxed text-text-secondaryLight dark:text-text-secondaryDark">{subtitle}</p>
        ) : null}
        <p className="text-xs text-text-tertiaryLight dark:text-text-tertiaryDark">최종 업데이트: {updatedAtLabel}</p>
      </header>

      <div className="space-y-10">
        {sections.map((section) => (
          <section
            key={section.id}
            id={section.id}
            className="scroll-mt-20 rounded-2xl border border-border-light bg-background-cardLight/80 p-6 shadow-sm transition-colors dark:border-border-dark dark:bg-background-cardDark/80"
          >
            <h2 className="text-lg font-semibold text-text-primaryLight dark:text-text-primaryDark">{section.title}</h2>
            {section.description ? (
              <p className="mt-2 text-sm leading-relaxed text-text-secondaryLight dark:text-text-secondaryDark">
                {section.description}
              </p>
            ) : null}
            <div className="mt-4 space-y-3">
              {section.contents.map((content, idx) => renderContent(content, idx))}
            </div>
          </section>
        ))}
      </div>
    </div>
  );
}

export default LegalDocumentPage;
