"use client";

import Link from "next/link";
import type { Route } from "next";
import type { ReactNode } from "react";

type Props = {
  title: string;
  subtitle?: string;
  children: ReactNode;
  backLink?: { href: Route; label: string };
};

export function AuthPageShell({ title, subtitle, children, backLink }: Props) {
  return (
    <div className="flex min-h-screen flex-col bg-canvas text-text-primary">
      <div className="mx-auto flex w-full max-w-md flex-1 flex-col px-6 py-12">
        {backLink ? (
          <Link href={backLink.href} className="mb-6 text-sm text-text-secondary hover:text-text-primary">
            &larr; {backLink.label}
          </Link>
        ) : null}
        <div className="rounded-2xl border border-border-hair/80 bg-surface-1/90 p-8 shadow-elevation-2 backdrop-blur-glass">
          <h1 className="text-2xl font-semibold">{title}</h1>
          {subtitle ? <p className="mt-2 text-sm text-text-secondary">{subtitle}</p> : null}
          <div className="mt-8 flex flex-col gap-6">{children}</div>
        </div>
      </div>
    </div>
  );
}

export default AuthPageShell;
