import { useMemo } from "react";

export interface CsvPreviewerProps {
  content: string;
  delimiter?: string;
  maxRows?: number;
}

export function parseCsv(text: string, delimiter = ","): Array<Array<string>> {
  const lines = text.trim().split(/\r?\n/);
  const rows: Array<Array<string>> = [];

  for (const line of lines) {
    if (!line.trim()) continue;
    // Simple CSV parser handling quotes
    const row: Array<string> = [];
    let insideQuote = false;
    let cell = "";

    for (let i = 0; i < line.length; i++) {
      const char = line[i];
      if (char === '"') {
        insideQuote = !insideQuote;
      } else if (char === delimiter && !insideQuote) {
        row.push(cell.trim());
        cell = "";
      } else {
        cell += char;
      }
    }
    row.push(cell.trim());
    rows.push(row);
  }

  return rows;
}

export function CsvPreviewer({
  content,
  delimiter = ",",
  maxRows = 100,
}: CsvPreviewerProps) {
  const rows = useMemo(
    () => parseCsv(content, delimiter),
    [content, delimiter],
  );

  if (rows.length === 0) {
    return (
      <div className="p-8 text-center text-xs text-slate-500 font-mono">
        (Empty CSV file)
      </div>
    );
  }

  const header = rows[0];
  const bodyRows = rows.slice(1, maxRows + 1);
  const hasMore = rows.length > maxRows + 1;

  return (
    <div className="space-y-2">
      <div className="overflow-x-auto rounded border border-slate-800 bg-slate-950">
        <table className="w-full text-left text-xs font-mono text-slate-300">
          <thead className="border-b border-slate-800 bg-slate-900/90 text-slate-400 font-semibold uppercase tracking-wider">
            <tr>
              <th className="px-3 py-2 w-10 text-slate-600 select-none">#</th>
              {header.map((col, idx) => (
                <th key={idx} className="px-3 py-2 border-r border-slate-800/60 last:border-0">
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60">
            {bodyRows.map((row, rIdx) => (
              <tr
                key={rIdx}
                className={
                  rIdx % 2 === 0
                    ? "bg-slate-950 hover:bg-slate-900/50"
                    : "bg-slate-900/30 hover:bg-slate-900/60"
                }
              >
                <td className="px-3 py-2 text-slate-600 select-none">
                  {rIdx + 1}
                </td>
                {row.map((cell, cIdx) => (
                  <td
                    key={cIdx}
                    className="px-3 py-2 whitespace-nowrap border-r border-slate-800/40 last:border-0"
                  >
                    {cell}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {hasMore && (
        <p className="text-[11px] text-slate-500 text-center font-mono">
          Showing first {maxRows} rows of {rows.length - 1} total rows.
        </p>
      )}
    </div>
  );
}
