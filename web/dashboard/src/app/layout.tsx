import type { Metadata } from "next";
import { Providers } from "@/lib/providers";
import "@/app/globals.css";

export const metadata: Metadata = {
  title: "K-Finance Dashboard",
  description: "K-Finance AI Copilot 사용자 대시보드"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ko" suppressHydrationWarning>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
