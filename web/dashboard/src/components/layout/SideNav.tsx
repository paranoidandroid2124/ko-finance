"use client";

import { LayoutDashboard, FileText, MessageSquare, Newspaper, Settings, Shield } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { Route } from "next";

type NavItem = { href: Route; label: string; icon: typeof LayoutDashboard };

const NAV_ITEMS: NavItem[] = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/filings", label: "Filings", icon: FileText },
  { href: "/news", label: "News", icon: Newspaper },
  { href: "/chat", label: "Chat", icon: MessageSquare },
  { href: "/admin", label: "Admin", icon: Shield },
  { href: "/settings", label: "Settings", icon: Settings }
];

export function SideNav() {
  const pathname = usePathname();

  return (
    <aside className="hidden min-h-screen w-64 flex-col border-r border-border-light bg-background-cardLight px-4 py-6 dark:border-border-dark dark:bg-background-cardDark lg:flex">
      <div className="px-3 py-2 text-lg font-semibold tracking-tight">
        K-Finance Copilot
        <p className="mt-1 text-xs font-medium text-text-secondaryLight dark:text-text-secondaryDark">
          Integrated filings, news, and RAG signals
        </p>
      </div>
      <nav className="mt-6 flex flex-1 flex-col gap-1">
        {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
          const isActive = href === "/" ? pathname === href : pathname.startsWith(href);
          const baseClasses =
            "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors hover:bg-primary/10 hover:text-primary dark:hover:bg-primary.dark/15";
          const activeClasses = isActive
            ? "bg-primary/10 text-primary dark:bg-primary.dark/15 dark:text-primary.dark"
            : "text-text-secondaryLight dark:text-text-secondaryDark";

          return (
            <Link key={href} href={href} className={`${baseClasses} ${activeClasses}`} aria-current={isActive ? "page" : undefined}>
              <Icon className="h-5 w-5" />
              <span>{label}</span>
            </Link>
          );
        })}
      </nav>
      <div className="rounded-lg border border-dashed border-border-light p-3 text-xs text-text-secondaryLight dark:border-border-dark dark:text-text-secondaryDark">
        <p className="font-semibold text-text-primaryLight dark:text-text-primaryDark">Need help?</p>
        <p className="mt-1">
          Review the runbooks, Langfuse traces, and infrastructure dashboards for quick triage.
        </p>
      </div>
    </aside>
  );
}
