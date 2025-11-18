import type { Metadata } from "next";
import { AppFooter } from "@/components/layout/AppFooter";
import { Providers } from "@/lib/providers";
import "@/app/globals.css";

export const metadata: Metadata = {
  title: "K-Finance Dashboard",
  description: "K-Finance AI Copilot 사용자 대시보드"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko" suppressHydrationWarning>
      <body className="min-h-screen bg-background text-text-primaryLight dark:bg-background-dark dark:text-text-primaryDark">
        <Providers>
          <div className="flex min-h-screen flex-col">
            <main className="flex-1">{children}</main>
            <AppFooter />
          </div>
        </Providers>
      </body>
    </html>
  );
}
