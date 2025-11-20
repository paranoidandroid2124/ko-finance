"use client";

import { Line, LineChart, CartesianGrid, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";

type StockLineChartProps = {
  title?: string;
  description?: string;
  label: string;
  unit?: string | null;
  data: Array<{ date: string; price: number }>;
};

const formatCurrency = (value: number, unit?: string | null) => {
  const formatted = new Intl.NumberFormat("ko-KR", { maximumFractionDigits: 2 }).format(value);
  return unit ? `${formatted} ${unit}` : formatted;
};

export function StockLineChart({ title, description, label, unit, data }: StockLineChartProps) {
  return (
    <div className="space-y-3">
      <div className="space-y-1">
        {title ? <p className="text-sm font-semibold text-white">{title}</p> : null}
        <p className="text-xs text-slate-400">{label}</p>
        {description ? <p className="text-xs text-slate-500">{description}</p> : null}
      </div>
      <div className="h-60 w-full rounded-xl border border-white/10 bg-black/40 p-3">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.06)" />
            <XAxis dataKey="date" tick={{ fontSize: 11, fill: "rgba(226,232,240,0.8)" }} tickLine={false} />
            <YAxis
              tick={{ fontSize: 11, fill: "rgba(226,232,240,0.8)" }}
              tickFormatter={(value) => formatCurrency(value as number, unit)}
              tickLine={false}
            />
            <Tooltip
              wrapperClassName="text-xs"
              contentStyle={{ background: "#0b1220", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 12 }}
              labelStyle={{ color: "#e2e8f0", fontWeight: 600 }}
              formatter={(value: number) => formatCurrency(value, unit)}
            />
            <Line type="monotone" dataKey="price" stroke="#60a5fa" strokeWidth={2.4} dot={false} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
