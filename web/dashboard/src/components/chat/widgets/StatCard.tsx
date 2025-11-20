"use client";

type StatCardProps = {
  title: string;
  value: string;
  description?: string;
};

export function StatCard({ title, value, description }: StatCardProps) {
  return (
    <div className="space-y-2 rounded-xl border border-white/10 bg-gradient-to-br from-blue-600/20 via-cyan-500/10 to-indigo-500/10 p-4 text-slate-100">
      <p className="text-xs font-semibold uppercase tracking-[0.2em] text-slate-300">{title}</p>
      <p className="text-2xl font-bold text-white">{value}</p>
      {description ? <p className="text-xs text-slate-300">{description}</p> : null}
    </div>
  );
}
