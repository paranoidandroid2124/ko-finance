"use client";

import Link from "next/link";
import { useEffect, useMemo, useRef, useState } from "react";
import { signOut, useSession } from "next-auth/react";
import { ChevronDown, CreditCard, HelpCircle, LogOut, Settings2 } from "lucide-react";
import clsx from "clsx";
import { SettingsOverlay } from "@/components/settings/SettingsOverlay";
import { getPlanLabel } from "@/lib/planTier";
import type { PlanTier } from "@/store/planStore";

export function UserMenu() {
  const { data: session, status } = useSession();
  const [open, setOpen] = useState(false);
  const [signingOut, setSigningOut] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const handleClick = (event: MouseEvent) => {
      if (!menuRef.current) {
        return;
      }
      if (!menuRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("mousedown", handleClick);
      document.removeEventListener("keydown", handleEscape);
    };
  }, []);

  const planLabel = useMemo(() => {
    const plan = session?.user ? (session.user as { plan?: string }).plan : undefined;
    return getPlanLabel((plan as PlanTier) ?? "free");
  }, [session]);

  const initials = useMemo(() => {
    const source = session?.user?.name || session?.user?.email || "";
    if (!source) {
      return "ME";
    }
    const chunks = source
      .split(/[\s@._-]+/)
      .filter(Boolean)
      .slice(0, 2);
    if (chunks.length === 0) {
      return source.slice(0, 2).toUpperCase();
    }
    return chunks
      .map((chunk) => chunk[0])
      .join("")
      .toUpperCase();
  }, [session]);

  const toggle = () => {
    if (status === "loading") {
      return;
    }
    setOpen((prev) => !prev);
  };

  const openSettings = () => {
    setOpen(false);
    setSettingsOpen(true);
  };

  const handleSignOut = async () => {
    setSigningOut(true);
    try {
      await signOut({ callbackUrl: "/auth/login" });
    } catch (error) {
      console.error("Failed to sign out", error);
    } finally {
      setSigningOut(false);
    }
  };

  if (!session) {
    return (
      <Link
        href="/auth/login"
        className="flex h-10 items-center gap-2 rounded-full border border-border-light px-4 text-sm font-semibold text-text-secondaryLight transition hover:border-primary hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 dark:border-border-dark dark:text-text-secondaryDark dark:hover:border-primary.dark dark:hover:text-primary.dark"
      >
        로그인
      </Link>
    );
  }

  return (
    <div className="relative" ref={menuRef}>
      <button
        type="button"
        onClick={toggle}
        className="flex items-center gap-2 rounded-full border border-border-light bg-gradient-to-tr from-primary to-accent-positive px-3 py-1 text-sm font-semibold text-white shadow-sm transition hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 dark:border-border-dark"
        aria-expanded={open}
        aria-haspopup="true"
      >
        <span className="flex h-7 w-7 items-center justify-center rounded-full bg-white/20 text-xs font-bold uppercase">
          {initials}
        </span>
        <ChevronDown className="h-4 w-4 opacity-80" aria-hidden />
      </button>

      {open ? (
        <div className="absolute right-0 z-50 mt-2 w-64 rounded-2xl border border-border-light bg-background-cardLight p-3 text-sm shadow-xl transition dark:border-border-dark dark:bg-background-cardDark">
          <div className="border-b border-border-light pb-3 dark:border-border-dark">
            <p className="text-xs font-semibold uppercase text-text-tertiaryLight dark:text-text-tertiaryDark">
              로그인 계정
            </p>
            <p className="mt-1 truncate text-sm font-medium text-text-primaryLight dark:text-text-primaryDark">
              {session.user?.email ?? "알 수 없는 이메일"}
            </p>
            <p className="text-xs text-text-secondaryLight dark:text-text-secondaryDark">{planLabel} 플랜</p>
          </div>

          <nav className="mt-3 space-y-1">
            <MenuLink icon={Settings2} label="설정" onClick={openSettings} />
            <MenuLink href="/pricing" icon={CreditCard} label="플랜 & 가격" />
            <MenuLink href="https://docs.kfinance.co/help" icon={HelpCircle} label="도움말" external />
          </nav>

          <button
            type="button"
            onClick={handleSignOut}
            disabled={signingOut}
            className={clsx(
              "mt-3 flex w-full items-center justify-center gap-2 rounded-xl border border-border-light px-3 py-2 text-sm font-semibold text-text-secondaryLight transition hover:border-primary hover:bg-primary/10 hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 dark:border-border-dark dark:text-text-secondaryDark dark:hover:border-primary.dark dark:hover:text-primary.dark",
              signingOut && "cursor-wait opacity-70",
            )}
          >
            <LogOut className="h-4 w-4" aria-hidden />
            {signingOut ? "로그아웃 중..." : "로그아웃"}
          </button>
        </div>
      ) : null}
      {settingsOpen ? <SettingsOverlay onClose={() => setSettingsOpen(false)} /> : null}
    </div>
  );
}

type MenuLinkProps = {
  href?: string;
  icon: typeof Settings2;
  label: string;
  external?: boolean;
  onClick?: () => void;
};

function MenuLink({ href, icon: Icon, label, external, onClick }: MenuLinkProps) {
  const shared = (
    <>
      <Icon className="h-4 w-4 text-text-tertiaryLight dark:text-text-tertiaryDark" aria-hidden />
      <span className="text-text-secondaryLight dark:text-text-secondaryDark">{label}</span>
    </>
  );

  if (onClick) {
    return (
      <button
        type="button"
        onClick={onClick}
        className="flex w-full items-center gap-2 rounded-lg px-2 py-2 text-left transition hover:bg-border-light/50 dark:hover:bg-white/10"
      >
        {shared}
      </button>
    );
  }

  if (external) {
    if (!href) {
      return null;
    }
    return (
      <a
        href={href}
        target="_blank"
        rel="noreferrer"
        className="flex items-center gap-2 rounded-lg px-2 py-2 transition hover:bg-border-light/50 dark:hover:bg-white/10"
      >
        {shared}
      </a>
    );
  }

  if (!href) {
    return null;
  }

  const nextHref = href as unknown as Parameters<typeof Link>[0]["href"];

  return (
    <Link
      href={nextHref}
      className="flex items-center gap-2 rounded-lg px-2 py-2 transition hover:bg-border-light/50 dark:hover:bg-white/10"
    >
      {shared}
    </Link>
  );
}
