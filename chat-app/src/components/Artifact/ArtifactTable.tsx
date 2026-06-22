interface ArtifactTableProps {
  columns: string[];
  rows: (string | number | null)[][];
}

export function ArtifactTable({ columns, rows }: ArtifactTableProps) {
  return (
    <div className="overflow-auto rounded-lg border border-white/10">
      <table className="w-full text-[13px]">
        <thead>
          <tr className="bg-white/5">
            {columns.map((col, i) => (
              <th key={i} className="px-3 py-2 text-left text-white/70 font-medium whitespace-nowrap border-b border-white/10">
                {col}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, ri) => (
            <tr key={ri} className="hover:bg-white/[0.03] transition-colors">
              {row.map((cell, ci) => (
                <td key={ci} className="px-3 py-1.5 text-white/60 whitespace-nowrap border-b border-white/5">
                  {cell === null ? <span className="text-white/20 italic">null</span> : String(cell)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
