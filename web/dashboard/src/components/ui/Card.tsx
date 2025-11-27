import clsx from "clsx";
import type { HTMLAttributes } from "react";

type CardVariant =
  | "primary"
  | "glass"
  | "raised"
  | "ghost"
  | "borderless"
  // legacy aliases
  | "default"
  | "highlight"
  | "data-container";

type CardPadding = "none" | "xs" | "sm" | "md" | "lg";

interface CardProps extends HTMLAttributes<HTMLDivElement> {
  variant?: CardVariant;
  padding?: CardPadding;
}

export function Card({
  variant = "primary",
  padding = "md",
  className,
  children,
  ...props
}: CardProps) {
  const resolvedVariant: CardVariant =
    variant === "default" ? "primary" : variant === "data-container" ? "raised" : variant === "highlight" ? "glass" : variant;

  return (
    <div
      className={clsx(
        "rounded-2xl transition-all duration-300 transition-motion-medium",
        resolvedVariant === "primary" && "bg-surface-1/95 border border-border-hair/70 shadow-elevation-1",
        resolvedVariant === "glass" && "bg-surface-1/80 border border-border-hair/50 shadow-card backdrop-blur-glass hover:border-primary/50",
        resolvedVariant === "raised" && "bg-surface-2/90 border border-border-hair/70 shadow-elevation-2",
        resolvedVariant === "ghost" && "border border-border-hair/40 bg-transparent shadow-none",
        resolvedVariant === "borderless" && "border-none shadow-none bg-transparent",
        padding === "none" && "p-0",
        padding === "xs" && "p-2.5",
        padding === "sm" && "p-4",
        padding === "md" && "p-5",
        padding === "lg" && "p-6 md:p-8",
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
}
