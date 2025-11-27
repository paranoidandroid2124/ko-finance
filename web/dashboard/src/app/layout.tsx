import type { Metadata } from "next";
import { Providers } from "@/lib/providers";
import { Background } from "@/components/ui/Background";
import "./globals.css";

export const metadata: Metadata = {
  title: "Nuvien | AI Financial Analyst",
  description: "Automated financial research and analysis platform.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="min-h-screen bg-canvas text-text-primary antialiased selection:bg-primary-glow/30">
        <Background />
        <Providers>
          <main className="flex min-h-screen flex-col">{children}</main>
        </Providers>
      </body>
    </html>
  );
}
