"use client";

type FinancialTableProps = {
  title?: string;
  description?: string;
  headers: string[];
  rows: string[][];
};

export function FinancialTable({ title, description, headers, rows }: FinancialTableProps) {
  return (
    <div className="space-y-3">
      <div className="space-y-1">
        {title ? <p className="text-sm font-semibold text-white">{title}</p> : null}
        {description ? <p className="text-xs text-slate-500">{description}</p> : null}
      </div>
      <div className="overflow-hidden rounded-xl border border-white/10 bg-black/30">
        <table className="min-w-full border-collapse text-sm text-slate-100">
          <thead className="bg-white/5 text-xs uppercase tracking-wide text-slate-400">
            <tr>
              {headers.map((header) => (
                <th key={header} className="px-4 py-3 text-left font-semibold">
                  {header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, rowIndex) => (
              <tr
                key={`${rowIndex}-${row[0] ?? rowIndex}`}
                className={rowIndex % 2 === 0 ? "bg-transparent" : "bg-white/5"}
              >
                {row.map((cell, cellIndex) => (
                  <td key={`${rowIndex}-${cellIndex}`} className="px-4 py-3 text-slate-200">
                    {cell}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
