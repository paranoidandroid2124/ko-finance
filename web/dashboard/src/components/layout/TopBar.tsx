"use client";

import { MoonStar, SunMedium } from "lucide-react";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";
import { AlertBell } from "../ui/AlertBell";

export function TopBar() {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const isDark = mounted ? theme === "dark" : false;

  return (
    <header className="flex flex-none items-center justify-between border-b border-border-light bg-background-cardLight px-6 py-4 shadow-sm transition-colors dark:border-border-dark dark:bg-background-cardDark">
      <div>
        <h1 className="text-lg font-semibold text-text-primaryLight dark:text-text-primaryDark">데이터 허브</h1>
        <p className="text-sm text-text-secondaryLight dark:text-text-secondaryDark">
          최신 공시·뉴스 업데이트와 RAG 분석을 한곳에서 확인하세요.
        </p>
      </div>
      <div className="flex items-center gap-3">
        <AlertBell />
        <button
          type="button"
          onClick={() => setTheme(isDark ? "light" : "dark")}
          className="flex h-10 w-10 items-center justify-center rounded-full border border-border-light text-text-secondaryLight transition-transform duration-150 hover:scale-[1.05] hover:border-primary hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 dark:border-border-dark dark:text-text-secondaryDark dark:hover:border-primary.dark dark:hover:text-primary.dark"
        >
          {isDark ? <SunMedium className="h-5 w-5" aria-hidden /> : <MoonStar className="h-5 w-5" aria-hidden />}
          <span className="sr-only">테마 전환</span>
        </button>
        <div className="flex h-10 w-10 items-center justify-center rounded-full bg-gradient-to-tr from-primary to-accent-positive text-sm font-semibold text-white ring-2 ring-primary/40">
          <span className="sr-only">사용자 프로필</span>
        </div>
      </div>
    </header>
  );
}

