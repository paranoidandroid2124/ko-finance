import clsx from "clsx";
import type { CSSProperties, HTMLAttributes } from "react";
import { useRef } from "react";

type SpotlightCardProps = HTMLAttributes<HTMLDivElement>;

/**
 * SpotlightCard renders a glassy card with a cursor-aware radial glow.
 * CSS custom properties are updated directly for smooth animation without re-renders.
 */
export default function SpotlightCard({
  className,
  children,
  style,
  onMouseMove,
  onMouseLeave,
  ...rest
}: SpotlightCardProps) {
  const divRef = useRef<HTMLDivElement>(null);

  const handleMouseMove = (event: React.MouseEvent<HTMLDivElement>) => {
    if (divRef.current) {
      const rect = divRef.current.getBoundingClientRect();
      const x = event.clientX - rect.left;
      const y = event.clientY - rect.top;
      divRef.current.style.setProperty("--mouse-x", `${x}px`);
      divRef.current.style.setProperty("--mouse-y", `${y}px`);
    }
    onMouseMove?.(event);
  };

  const handleMouseLeave = (event: React.MouseEvent<HTMLDivElement>) => {
    if (divRef.current) {
      divRef.current.style.removeProperty("--mouse-x");
      divRef.current.style.removeProperty("--mouse-y");
    }
    onMouseLeave?.(event);
  };

  const inlineStyle: CSSProperties = {
    ...style,
    "--mouse-x": "50%",
    "--mouse-y": "50%",
  } as CSSProperties;

  return (
    <div
      ref={divRef}
      className={clsx(
        "group relative overflow-hidden rounded-3xl border border-white/5 bg-white/[0.03]",
        "backdrop-blur-lg transition duration-500 ease-out hover:-translate-y-1 hover:border-white/20",
        "before:pointer-events-none before:absolute before:-inset-px before:rounded-[inherit]",
        "before:bg-[radial-gradient(circle_at_var(--mouse-x)_var(--mouse-y),rgba(99,102,241,0.45),transparent_70%)]",
        "before:opacity-0 before:transition-opacity before:duration-300 group-hover:before:opacity-100",
        "after:pointer-events-none after:absolute after:inset-[1px] after:rounded-[inherit] after:border after:border-white/5 after:opacity-70",
        className,
      )}
      style={inlineStyle}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      {...rest}
    >
      <div className="relative z-10">{children}</div>
      <div className="pointer-events-none absolute inset-0 rounded-[inherit] bg-gradient-to-b from-white/10 via-transparent to-transparent opacity-40" />
    </div>
  );
}
