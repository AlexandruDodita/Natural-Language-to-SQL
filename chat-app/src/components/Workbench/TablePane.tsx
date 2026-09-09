import { useMemo, useState } from 'react';
import type { ArtifactData, CellValue, ColumnKind } from '../../types';
import { fmtNum } from '../../lib/format';
import { inferKinds, isNumeric, toNum } from '../../lib/shape';

interface TablePaneProps {
  artifact: ArtifactData;
  maxRows?: number | null;
}

const KIND_BADGE: Record<ColumnKind, string> = {
  int: 'int',
  num: 'num',
  date: 'date',
  month: 'month',
  text: 'text',
  bool: 'bool',
};

/** A 12px-tall column profile drawn from the actual values, not from the type. */
function Profile({ values, kind }: { values: CellValue[]; kind: ColumnKind }) {
  const bars = useMemo(() => {
    if (isNumeric(kind)) {
      const nums = values.map(toNum).filter((v): v is number => v !== null);
      if (nums.length < 2) return [];
      const min = Math.min(...nums);
      const max = Math.max(...nums);
      const n = 12;
      const width = (max - min) / n || 1;
      const counts = new Array(n).fill(0);
      nums.forEach(v => {
        counts[Math.min(n - 1, Math.floor((v - min) / width))] += 1;
      });
      const peak = Math.max(...counts, 1);
      return counts.map(c => c / peak);
    }
    const freq = new Map<string, number>();
    values.forEach(v => {
      const k = v === null ? '∅' : String(v);
      freq.set(k, (freq.get(k) ?? 0) + 1);
    });
    const top = [...freq.values()].sort((a, b) => b - a).slice(0, 12);
    const peak = Math.max(...top, 1);
    return top.map(c => c / peak);
  }, [values, kind]);

  if (!bars.length) return null;
  const w = 100 / bars.length;

  return (
    <svg className="prof" viewBox="0 0 100 12" preserveAspectRatio="none" aria-hidden="true">
      {bars.map((h, i) => (
        <rect
          key={i}
          x={i * w + 0.4}
          y={12 - Math.max(1, h * 12)}
          width={Math.max(0.8, w - 0.8)}
          height={Math.max(1, h * 12)}
          fill="var(--accent)"
          opacity={0.35}
        />
      ))}
    </svg>
  );
}

export function TablePane({ artifact, maxRows }: TablePaneProps) {
  const [filter, setFilter] = useState('');
  const [group, setGroup] = useState('none');
  const [sort, setSort] = useState<{ col: number | null; dir: 1 | -1 }>({ col: null, dir: 1 });

  const kinds = useMemo(() => inferKinds(artifact), [artifact]);
  const categorical = artifact.columns.filter((_, i) => !isNumeric(kinds[i]));

  // group-by → sum every numeric column, count the rows
  const grouped = useMemo(() => {
    if (group === 'none') return { columns: artifact.columns, rows: artifact.rows, kinds };
    const gi = artifact.columns.indexOf(group);
    if (gi < 0) return { columns: artifact.columns, rows: artifact.rows, kinds };

    const numericIdx = artifact.columns.map((_, i) => i).filter(i => isNumeric(kinds[i]));
    const columns = [group, 'rows', ...numericIdx.map(i => `sum(${artifact.columns[i]})`)];
    const buckets = new Map<string, { key: CellValue; n: number; sums: number[] }>();

    for (const row of artifact.rows) {
      const k = String(row[gi] ?? '');
      if (!buckets.has(k)) buckets.set(k, { key: row[gi], n: 0, sums: numericIdx.map(() => 0) });
      const b = buckets.get(k)!;
      b.n += 1;
      numericIdx.forEach((ci, j) => {
        b.sums[j] += toNum(row[ci]) ?? 0;
      });
    }

    return {
      columns,
      rows: [...buckets.values()].map(b => [b.key, b.n, ...b.sums] as CellValue[]),
      kinds: ['text' as ColumnKind, 'int' as ColumnKind, ...numericIdx.map(() => 'num' as ColumnKind)],
    };
  }, [artifact, group, kinds]);

  const filtered = useMemo(() => {
    const q = filter.trim().toLowerCase();
    if (!q) return grouped.rows;
    return grouped.rows.filter(r => r.some(c => String(c ?? '').toLowerCase().includes(q)));
  }, [grouped.rows, filter]);

  const sorted = useMemo(() => {
    if (sort.col === null) return filtered;
    const ci = sort.col;
    const numeric = isNumeric(grouped.kinds[ci]);
    return [...filtered].sort((a, b) => {
      if (numeric) return ((toNum(a[ci]) ?? 0) - (toNum(b[ci]) ?? 0)) * sort.dir;
      return String(a[ci] ?? '').localeCompare(String(b[ci] ?? '')) * sort.dir;
    });
  }, [filtered, sort, grouped.kinds]);

  const total = grouped.rows.length;

  return (
    <>
      <div className="tbl-tools">
        <input
          className="ctl"
          style={{ flex: 1, minWidth: 140 }}
          placeholder="Filter rows…"
          value={filter}
          onChange={e => setFilter(e.target.value)}
        />
        <select className="ctl" value={group} onChange={e => setGroup(e.target.value)}>
          <option value="none">No grouping</option>
          {categorical.map(c => (
            <option key={c} value={c}>
              Group by {c} (sum)
            </option>
          ))}
        </select>
        <button
          className="btn btn-sm"
          onClick={() => {
            setFilter('');
            setGroup('none');
            setSort({ col: null, dir: 1 });
          }}
        >
          Reset
        </button>
      </div>

      <div className="tbl-wrap">
        <table className="grid">
          <thead>
            <tr>
              {grouped.columns.map((c, i) => (
                <th
                  key={c}
                  onClick={() =>
                    setSort(s => (s.col === i ? { col: i, dir: s.dir === 1 ? -1 : 1 } : { col: i, dir: 1 }))
                  }
                  title="Sort"
                >
                  <span className="th-in">
                    {c}
                    <span className="ty">{KIND_BADGE[grouped.kinds[i]]}</span>
                    {sort.col === i && <span className="sort">{sort.dir === 1 ? '▲' : '▼'}</span>}
                  </span>
                  <Profile values={grouped.rows.map(r => r[i])} kind={grouped.kinds[i]} />
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.map((row, ri) => (
              <tr key={ri}>
                {row.map((cell, ci) => (
                  <td key={ci} className={isNumeric(grouped.kinds[ci]) ? 'num' : undefined}>
                    {cell === null || cell === undefined ? (
                      <span className="null">null</span>
                    ) : isNumeric(grouped.kinds[ci]) ? (
                      fmtNum(cell)
                    ) : (
                      String(cell)
                    )}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="tbl-foot">
        <span>
          showing {sorted.length} of {total} row{total === 1 ? '' : 's'}
        </span>
        {maxRows ? <span className="mono">max_rows = {maxRows}</span> : null}
        {artifact.truncated && (
          <span className="chip chip-warn">
            <span className="dot" />
            truncated at the row cap — this is not the whole result
          </span>
        )}
      </div>
    </>
  );
}
