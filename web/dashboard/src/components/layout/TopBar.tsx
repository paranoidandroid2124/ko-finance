import { Bell, MoonStar, SunMedium } from "lucide-react";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";

export function TopBar() {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  const isDark = mounted ? theme === "dark" : false;

  return (
    <header className="flex flex-none items-center justify-between border-b border-border-light bg-background-cardLight px-6 py-4 shadow-sm dark:border-border-dark dark:bg-background-cardDark">
      <div>
        <h1 className="text-lg font-semibold">데이터 허브</h1>
        <p className="text-sm text-text-secondaryLight dark:text-text-secondaryDark">
          최신 공시, 뉴스, RAG 분석을 한곳에서 확인하세요.
        </p>
      </div>
      <div className="flex items-center gap-3">
        <button className="rounded-full border border-border-light p-2 text-text-secondaryLight transition-colors hover:border-primary hover:text-primary dark:border-border-dark dark:text-text-secondaryDark dark:hover:border-primary.dark dark:hover:text-primary.dark">
          <Bell className="h-5 w-5" aria-hidden />
          <span className="sr-only">알림 보기</span>
        </button>
        <button
          onClick={() => setTheme(isDark ? "light" : "dark")}
          className="rounded-full border border-border-light p-2 text-text-secondaryLight transition-colors hover:border-primary hover:text-primary dark:border-border-dark dark:text-text-secondaryDark dark:hover:border-primary.dark dark:hover:text-primary.dark"
        >
          {isDark ? <SunMedium className="h-5 w-5" aria-hidden /> : <MoonStar className="h-5 w-5" aria-hidden />}
          <span className="sr-only">테마 전환</span>
        </button>
        <div className="h-10 w-10 rounded-full bg-gradient-to-tr from-primary to-accent-positive text-sm font-semibold text-white ring-2 ring-primary/40">
          <span className="sr-only">사용자 프로필</span>
        </div>
      </div>
    </header>
  );
}

