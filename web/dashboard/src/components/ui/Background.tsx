"use client";

import { useTheme } from "next-themes";
import { useMemo } from "react";

/**
 * Unified background system:
 * - Base gradient (light/dark variant)
 * - Aurora glow (brand cyan + orchid)
 * - Subtle grid lines
 * - Noise overlay + vignette
 *
 * Theme-aware so light mode is actually bright.
 */
export function Background() {
  const { resolvedTheme } = useTheme();
  const isDark = useMemo(() => resolvedTheme === "dark", [resolvedTheme]);

  const baseGradient = isDark
    ? "bg-[radial-gradient(circle_at_20%_20%,rgba(88,225,255,0.08),transparent_45%),radial-gradient(circle_at_80%_12%,rgba(189,123,255,0.08),transparent_42%),linear-gradient(180deg,rgba(3,7,18,0.96),rgba(6,10,22,0.9))]"
    : "bg-[radial-gradient(circle_at_25%_15%,rgba(88,225,255,0.12),transparent_48%),radial-gradient(circle_at_80%_8%,rgba(189,123,255,0.1),transparent_46%),linear-gradient(180deg,rgba(240,244,252,0.96),rgba(225,233,246,0.92))]";

  const vignette = isDark
    ? "bg-[radial-gradient(circle_at_center,transparent_0%,rgba(3,7,18,0.82)_100%)]"
    : "bg-[radial-gradient(circle_at_center,transparent_0%,rgba(230,236,246,0.65)_100%)]";

  const gridOpacity = isDark ? "opacity-[0.08]" : "opacity-[0.04]";
  const noiseOpacity = isDark ? "opacity-[0.16]" : "opacity-[0.08]";

  return (
    <div className="fixed inset-0 -z-50 h-full w-full overflow-hidden">
      {/* Base gradient */}
      <div className={`absolute inset-0 ${baseGradient}`} />

      {/* Aurora sweep */}
      <div className="absolute inset-0">
        <div className={`absolute -left-[12%] -top-[18%] h-[42rem] w-[42rem] rounded-full ${isDark ? "bg-accent-brand/14" : "bg-accent-brand/18"} blur-[220px]`} />
        <div className={`absolute right-[-6%] top-[8%] h-[34rem] w-[34rem] rounded-full ${isDark ? "bg-accent-glow/12" : "bg-accent-glow/16"} blur-[200px]`} />
        <div className={`absolute left-[18%] bottom-[-12%] h-[32rem] w-[48rem] rounded-full ${isDark ? "bg-accent-brand/10" : "bg-accent-brand/14"} blur-[190px]`} />
      </div>

      {/* Grid overlay */}
      <div className={`absolute inset-0 ${gridOpacity}`}>
        <div className="absolute inset-0 bg-[linear-gradient(0deg,transparent_95%,rgba(255,255,255,0.6)_100%),linear-gradient(90deg,transparent_95%,rgba(255,255,255,0.6)_100%)] bg-[size:80px_80px]" />
      </div>

      {/* Noise texture */}
      <div className={`absolute inset-0 z-[1] bg-noise-pattern ${noiseOpacity} mix-blend-overlay`} />

      {/* Vignette */}
      <div className={`absolute inset-0 z-[2] ${vignette}`} />
    </div>
  );
}
