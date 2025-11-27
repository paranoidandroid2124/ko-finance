import clsx from "clsx";
import type { PropsWithChildren } from "react";

type DeepTechLayoutProps = PropsWithChildren<{
  className?: string;
}>;

/**
 * DeepTechLayout composes the animated background layers (grid + aurora glow)
 * and ensures the actual page content renders above them.
 */
export default function DeepTechLayout({ children, className }: DeepTechLayoutProps) {
  return (
    <div className="relative min-h-screen overflow-hidden bg-canvas text-text-primary">
      <div className="pointer-events-none fixed inset-0 z-0">
        <div
          className={clsx(
            "absolute inset-0 opacity-40",
            "bg-[linear-gradient(rgba(37,45,89,0.35)_1px,transparent_1px),linear-gradient(90deg,rgba(37,45,89,0.35)_1px,transparent_1px)]",
            "bg-[size:120px_120px]",
            "animate-grid-move",
          )}
        />
        <div
          className={clsx(
            "absolute left-1/2 top-[-5%] h-[520px] w-[720px] -translate-x-1/2 rounded-full",
            "bg-[radial-gradient(circle,rgba(88,113,255,0.45)_0%,transparent_70%)]",
            "blur-[180px] opacity-70 animate-pulse-glow",
          )}
        />
        <div
          className={clsx(
            "absolute right-[-10%] top-1/3 h-[360px] w-[360px] rounded-full",
            "bg-[radial-gradient(circle,rgba(34,211,238,0.3),transparent_65%)]",
            "blur-[160px] opacity-70",
          )}
        />
      </div>
      <div className={clsx("relative z-10", className)}>{children}</div>
    </div>
  );
}
