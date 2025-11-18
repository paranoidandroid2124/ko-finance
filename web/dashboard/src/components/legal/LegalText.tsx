"use client";

import type { ComponentPropsWithoutRef, ElementType } from "react";
import classNames from "classnames";
import { LEGAL_COPY, type LegalSection, type LegalSectionKey } from "./LegalCopy";

type LegalTextProps<S extends LegalSection> = {
  section: S;
  item: LegalSectionKey<S>;
  as?: ElementType;
  className?: string;
} & Omit<ComponentPropsWithoutRef<"p">, "children">;

/**
 * Generic renderer that spits out the configured legal copy string.
 * Using an explicit component keeps future i18n/markup decisions in one place.
 */
export function LegalText<S extends LegalSection>({ section, item, as: Tag = "p", className, ...rest }: LegalTextProps<S>) {
  const text = LEGAL_COPY[section][item];

  if (!text) {
    return null;
  }

  return (
    <Tag
      {...rest}
      className={classNames(
        "whitespace-pre-line text-xs leading-relaxed text-text-secondaryLight dark:text-text-secondaryDark",
        className
      )}
    >
      {text}
    </Tag>
  );
}

type LegalSnippetProps<S extends LegalSection> = Omit<LegalTextProps<S>, "section" | "item">;

type LegalTextComponentOptions = {
  defaultAs?: ElementType;
  defaultClassName?: string;
};

export function createLegalText<S extends LegalSection, K extends LegalSectionKey<S>>(
  section: S,
  item: K,
  options?: LegalTextComponentOptions
) {
  const Component = ({ className, as, ...rest }: LegalSnippetProps<S>) => {
    return (
      <LegalText
        {...rest}
        section={section}
        item={item}
        as={(as ?? options?.defaultAs) as ElementType}
        className={classNames(options?.defaultClassName, className)}
      />
    );
  };
  Component.displayName = `LegalText(${section}.${String(item)})`;
  return Component;
}

export type { LegalTextProps };
