import clsx from "clsx";
import type { ButtonHTMLAttributes, ReactNode } from "react";

type ButtonVariant = "solid" | "outline" | "ghost" | "subtle";
type ButtonTone = "brand" | "neutral" | "danger" | "success";
type ButtonSize = "sm" | "md" | "lg" | "icon";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  tone?: ButtonTone;
  size?: ButtonSize;
  icon?: ReactNode;
  iconRight?: ReactNode;
  loading?: boolean;
  fullWidth?: boolean;
};

const sizeClasses: Record<ButtonSize, string> = {
  sm: "h-9 px-3 text-sm gap-2 rounded-lg",
  md: "h-10 px-4 text-sm gap-2 rounded-lg",
  lg: "h-11 px-5 text-base gap-2 rounded-xl",
  icon: "h-10 w-10 items-center justify-center rounded-lg"
};

const toneClasses: Record<ButtonTone, { solid: string; outline: string; ghost: string; subtle: string }> = {
  brand: {
    solid:
      "bg-primary text-background-dark border border-transparent shadow-glow-brand hover:bg-primary/90 focus-visible:ring-2 focus-visible:ring-primary/30",
    outline:
      "border border-primary/60 text-primary hover:bg-primary/10 focus-visible:ring-2 focus-visible:ring-primary/25",
    ghost: "text-primary border border-transparent hover:bg-surface-2/70",
    subtle: "bg-surface-2/80 text-text-primary border border-border-hair/60 hover:border-primary/50"
  },
  neutral: {
    solid: "bg-surface-2 text-text-primary border border-border-hair/70 shadow-subtle hover:bg-surface-2/90",
    outline: "border border-border-hair/70 text-text-primary hover:bg-surface-2/80",
    ghost: "text-text-secondary border border-transparent hover:bg-surface-2/70",
    subtle: "bg-surface-1/80 text-text-secondary border border-border-hair/50 hover:text-text-primary"
  },
  danger: {
    solid:
      "bg-accent-rose text-background-dark border border-transparent shadow-subtle hover:bg-accent-rose/90 focus-visible:ring-2 focus-visible:ring-accent-rose/30",
    outline:
      "border border-accent-rose/70 text-accent-rose hover:bg-accent-rose/10 focus-visible:ring-2 focus-visible:ring-accent-rose/25",
    ghost: "text-accent-rose border border-transparent hover:bg-accent-rose/10",
    subtle: "bg-surface-2/80 text-accent-rose border border-accent-rose/30 hover:border-accent-rose/50"
  },
  success: {
    solid:
      "bg-accent-emerald text-background-dark border border-transparent shadow-subtle hover:bg-accent-emerald/90 focus-visible:ring-2 focus-visible:ring-accent-emerald/30",
    outline:
      "border border-accent-emerald/70 text-accent-emerald hover:bg-accent-emerald/10 focus-visible:ring-2 focus-visible:ring-accent-emerald/25",
    ghost: "text-accent-emerald border border-transparent hover:bg-accent-emerald/10",
    subtle: "bg-surface-2/80 text-accent-emerald border border-accent-emerald/30 hover:border-accent-emerald/50"
  }
};

export function Button({
  variant = "solid",
  tone = "brand",
  size = "md",
  icon,
  iconRight,
  loading,
  fullWidth,
  className,
  children,
  disabled,
  ...props
}: ButtonProps) {
  const palette = toneClasses[tone][variant];
  const isDisabled = disabled || loading;
  return (
    <button
      type="button"
      className={clsx(
        "inline-flex select-none items-center justify-center font-semibold transition duration-200 focus-visible:outline-none transition-motion-fast",
        sizeClasses[size],
        palette,
        fullWidth && "w-full",
        isDisabled && "opacity-60 cursor-not-allowed",
        className
      )}
      disabled={isDisabled}
      aria-disabled={isDisabled}
      {...props}
    >
      {loading ? (
        <span className="h-4 w-4 animate-spin rounded-full border-2 border-border-hair/60 border-t-transparent" aria-hidden />
      ) : (
        icon
      )}
      <span className={clsx(size === "icon" && "sr-only")}>{children}</span>
      {iconRight}
    </button>
  );
}
