import type { Metadata } from "next";
import { Providers } from "@/lib/providers";
import "@/app/globals.css";

export const metadata: Metadata = {
  title: "Nuvien Dashboard",
  description: "Nuvien AI Copilot 사용자 대시보드"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko" suppressHydrationWarning>
      <body className="min-h-screen bg-background-dark text-slate-100 antialiased selection:bg-blue-500/30">
        <Providers>
          <main className="flex min-h-screen flex-col">{children}</main>
        </Providers>
      </body>
    </html>
  );
}
