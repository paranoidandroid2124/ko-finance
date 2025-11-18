"use client";

import clsx from "clsx";
import Link from "next/link";
import { usePathname } from "next/navigation";

type SettingsSectionNavProps = {
  className?: string;
};

const NAV_SECTIONS: Array<{ href: string; label: string }> = [
  { href: "/settings", label: "ì¼ë°˜ ì„¤ì •" },
  { href: "/settings/privacy", label: "ê°œì¸ì •ë³´Â·ë°ì´í„° ê´€ë¦¬" },
];

export function SettingsSectionNav({ className }: SettingsSectionNavProps) {
  const pathname = usePathname() ?? "";

  return (
    <div
      className={clsx(
        "rounded-2xl border border-border-light bg-background-cardLight px-4 py-3 shadow-sm dark:border-border-dark dark:bg-background-cardDark",
        className,
      )}
    >
      <nav className="flex flex-wrap gap-2 text-sm font-medium text-text-secondaryLight dark:text-text-secondaryDark">
        {NAV_SECTIONS.map((item) => {
          const isRoot = item.href === "/settings";
          const isActive = isRoot
            ? pathname === item.href
            : pathname === item.href || pathname.startsWith(`${item.href}/`);
          return (
            <Link
              key={item.href}
              href={item.href as unknown as Parameters<typeof Link>[0]["href"]}
              className={clsx(
                "rounded-full px-4 py-1.5 transition",
                isActive
                  ? "bg-primary/10 text-primary dark:bg-primary.dark/20 dark:text-primary.dark"
                  : "hover:bg-border-light/60 hover:text-text-primaryLight dark:hover:bg-border-dark/60 dark:hover:text-text-primaryDark",
              )}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>
    </div>
  );
}
