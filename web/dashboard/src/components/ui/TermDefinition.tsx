"use client";

type TermDefinitionProps = {
  term: string;
  description: string;
  tone?: "default" | "positive" | "negative";
};

const toneStyles: Record<NonNullable<TermDefinitionProps["tone"]>, string> = {
  default: "border-white/10 text-slate-200",
  positive: "border-emerald-400/50 text-emerald-200",
  negative: "border-rose-400/50 text-rose-200",
};

export function TermDefinition({ term, description, tone = "default" }: TermDefinitionProps) {
  return (
    <span className={`term-definition group/term relative inline-flex items-center gap-1 rounded-full border ${toneStyles[tone]} px-3 py-1 text-xs`}>
      {term}
      <span className="text-[10px] text-slate-400">ⓘ</span>
      <span className="pointer-events-none absolute left-1/2 top-full z-30 hidden w-48 -translate-x-1/2 translate-y-2 rounded-xl border border-white/10 bg-slate-900/95 px-3 py-2 text-[10px] text-slate-200 shadow-lg group-hover/term:block">
        {description}
      </span>
    </span>
  );
}

export default TermDefinition;
