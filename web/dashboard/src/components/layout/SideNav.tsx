"use client";

import {
  Building2,
  CreditCard,
  LayoutDashboard,
  FileText,
  MessageSquare,
  Newspaper,
  Radar,
  Settings,
  Shield,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { Route } from "next";

type NavItem = { href: Route; label: string; icon: typeof LayoutDashboard };

const NAV_ITEMS: NavItem[] = [
  { href: "/", label: "한눈에 보기", icon: LayoutDashboard },
  { href: "/watchlist", label: "워치리스트", icon: Radar },
  { href: "/news", label: "뉴스", icon: Newspaper },
  { href: "/filings", label: "공시 자료", icon: FileText },
  { href: "/company", label: "기업 살펴보기", icon: Building2 },
  { href: "/chat", label: "대화", icon: MessageSquare },
  { href: "/pricing", label: "플랜 & 가격", icon: CreditCard },
  { href: "/admin", label: "운영 콘솔", icon: Shield },
  { href: "/settings", label: "설정", icon: Settings }
];

export function SideNav() {
  const pathname = usePathname();

  return (
    <aside className="hidden min-h-screen w-64 flex-col border-r border-border-light bg-background-cardLight px-4 py-6 dark:border-border-dark dark:bg-background-cardDark lg:flex">
      <div className="px-3 py-2 text-lg font-semibold tracking-tight">
        K-Finance Copilot
        <p className="mt-1 text-xs font-medium text-text-secondaryLight dark:text-text-secondaryDark">
          공시·뉴스·RAG 신호를 한곳에서 돌봐드려요
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
        <p className="font-semibold text-text-primaryLight dark:text-text-primaryDark">도움이 필요하신가요?</p>
        <p className="mt-1">
          운영 런북과 Langfuse 트레이스, 인프라 대시보드를 살펴보시면 빠르게 정리할 수 있어요.
        </p>
      </div>
    </aside>
  );
}

