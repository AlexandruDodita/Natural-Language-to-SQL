import type {
  ArtifactData,
  CellValue,
  ChartSpec,
  ChartSuggestion,
  ColumnKind,
} from '../types';

// ---------------------------------------------------------------------------
// Column typing
//
// The result set arrives untyped — psycopg numerics come back as strings — so
// the type of a column is inferred from its values, once, and reused by the
// table (alignment, badge, profile) and by the chart suggester.
// ---------------------------------------------------------------------------
const DATE_RE = /^\d{4}-\d{2}-\d{2}([ T]|$)/;
const MONTH_RE = /^\d{4}-(0[1-9]|1[0-2])$/;

export function toNum(v: CellValue): number | null {
  if (v === null || v === undefined || v === '') return null;
  if (typeof v === 'number') return Number.isFinite(v) ? v : null;
  if (typeof v === 'boolean') return v ? 1 : 0;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

export function inferKind(values: CellValue[]): ColumnKind {
  const seen = values.filter(v => v !== null && v !== undefined && v !== '');
  if (!seen.length) return 'text';

  if (seen.every(v => typeof v === 'boolean')) return 'bool';

  if (seen.every(v => typeof v === 'string' && MONTH_RE.test(v))) return 'month';
  if (seen.every(v => typeof v === 'string' && DATE_RE.test(v))) return 'date';

  const nums = seen.map(toNum);
  if (nums.every(n => n !== null)) {
    return (nums as number[]).every(n => Number.isInteger(n)) ? 'int' : 'num';
  }
  return 'text';
}

export function inferKinds(artifact: ArtifactData): ColumnKind[] {
  return artifact.columns.map((_, i) => inferKind(artifact.rows.map(r => r[i])));
}

export const isNumeric = (k: ColumnKind) => k === 'int' || k === 'num';

// ---------------------------------------------------------------------------
// Shape profile
// ---------------------------------------------------------------------------
export interface ShapeProfile {
  kinds: ColumnKind[];
  cats: string[];
  nums: string[];
  times: string[];
  distinct: Record<string, number>;
  n: number;
}

export function profile(artifact: ArtifactData): ShapeProfile {
  const kinds = inferKinds(artifact);
  const cats: string[] = [];
  const nums: string[] = [];
  const times: string[] = [];

  kinds.forEach((k, i) => {
    // A date column is a time *axis* only when the result is ordered by it,
    // which in practice means it is the leading column. `first_seen` sitting in
    // column 4 of a ranking is a label, not a series index.
    if (k === 'month' || (k === 'date' && i === 0)) times.push(artifact.columns[i]);
    else if (isNumeric(k)) nums.push(artifact.columns[i]);
    else cats.push(artifact.columns[i]);
  });

  const distinct: Record<string, number> = {};
  artifact.columns.forEach((c, i) => {
    distinct[c] = new Set(artifact.rows.map(r => String(r[i]))).size;
  });

  return { kinds, cats, nums, times, distinct, n: artifact.rows.length };
}

export function shapeLine(p: ShapeProfile): string {
  const bits = [`${p.n} row${p.n === 1 ? '' : 's'}`];
  if (p.cats.length) bits.push(`${p.cats.length} categorical`);
  if (p.nums.length) bits.push(`${p.nums.length} numeric`);
  bits.push(`${p.times.length} temporal`);
  return bits.join(' · ');
}

// ---------------------------------------------------------------------------
// Shape → ranked chart suggestions
//
// `rank` is "how well does this read for this shape" — lower is better, so the
// first chip is what the system would pick on its own.
// ---------------------------------------------------------------------------
export function suggestions(artifact: ArtifactData): ChartSuggestion[] {
  const p = profile(artifact);
  const out: ChartSuggestion[] = [];
  const add = (
    rank: number,
    type: ChartSuggestion['type'],
    label: string,
    why: string,
    patch: Partial<ChartSpec> = {},
  ) => out.push({ rank, type, label, why, patch: { type, ...patch } });

  const many = p.n >= 20;
  const col = (name: string) => artifact.columns.indexOf(name);

  if (p.n === 1 && p.nums.length >= 1 && p.cats.length === 0)
    add(0, 'kpi', 'Big number', 'single scalar', { x: null, y: [p.nums[0]] });

  if (p.times.length === 1 && p.cats.length === 1 && p.nums.length === 1) {
    add(1, 'facet', 'Small multiples', `${p.distinct[p.cats[0]]} panels, shared scale`, {
      x: p.times[0], y: [p.nums[0]], series: p.cats[0],
    });
    add(2, 'line', 'Multi-line', `${p.distinct[p.cats[0]]} series over time`, {
      x: p.times[0], y: [p.nums[0]], series: p.cats[0],
    });
    add(5, 'heat', 'Heatmap', `time × ${p.cats[0]} matrix`, {
      x: p.times[0], y: [p.nums[0]], series: p.cats[0],
    });
  } else if (p.times.length === 1 && p.nums.length >= 1) {
    add(1, 'line', 'Line', `${p.nums.length} measure${p.nums.length > 1 ? 's' : ''} over time`, {
      x: p.times[0], y: p.nums.slice(0, 3),
    });
    if (p.nums.length >= 2)
      add(2, 'combo', 'Dual axis', `mixed units (${p.nums[0]} vs ${p.nums[p.nums.length - 1]})`, {
        x: p.times[0],
        y: p.nums.slice(0, p.nums.length - 1),
        secondary: p.nums[p.nums.length - 1],
      });
    add(4, 'area', 'Area', 'cumulative reading', { x: p.times[0], y: [p.nums[0]] });
  }

  if (p.nums.length >= 2 && many)
    add(1, 'scatter', 'Scatter + trend', `correlation over ${p.n} rows`, {
      x: p.nums[0], y: [p.nums[1]], series: p.cats[1] || p.cats[0] || null, trendline: true,
    });
  if (p.nums.length >= 1 && many)
    add(3, 'hist', 'Histogram', `distribution of ${p.nums[p.nums.length - 1]}`, {
      x: null, y: [p.nums[p.nums.length - 1]],
    });

  if (!p.times.length && p.cats.length >= 1 && p.nums.length >= 1) {
    const wide =
      p.distinct[p.cats[0]] > 8 ||
      artifact.rows.some(r => String(r[col(p.cats[0])] ?? '').length > 14);
    add(
      p.distinct[p.cats[0]] <= 15 ? 2 : 6,
      wide ? 'hbar' : 'bar',
      wide ? 'Bars (horizontal)' : 'Bars',
      `${p.distinct[p.cats[0]]} categories, ${wide ? 'long labels' : '1 measure'}`,
      { x: p.cats[0], y: [p.nums[0]] },
    );
    const yi = col(p.nums[0]);
    if (
      p.nums.length === 1 &&
      p.n <= 6 &&
      artifact.rows.every(r => (toNum(r[yi]) ?? 0) >= 0)
    )
      add(4, 'pie', 'Donut', `part-of-whole, ${p.n} slices`, { x: p.cats[0], y: [p.nums[0]] });
  }

  if (!p.times.length && p.cats.length >= 1 && p.nums.length >= 2 && p.distinct[p.cats[0]] <= 15) {
    add(2, 'bar', 'Grouped bars', `${p.nums.length} measures per category`, {
      x: p.cats[0], y: p.nums, stacked: false,
    });
    add(3, 'bar', 'Stacked bars', 'composition per category', {
      x: p.cats[0], y: p.nums, stacked: true,
    });
  }

  if (!out.length) add(0, 'none', 'Table only', 'no numeric measure to plot');
  return out.sort((a, b) => a.rank - b.rank);
}

// ---------------------------------------------------------------------------
// Spec
// ---------------------------------------------------------------------------
export const EMPTY_SPEC: ChartSpec = {
  type: 'none',
  title: '',
  x: null,
  y: [],
  series: null,
  secondary: null,
  stacked: false,
  normalize: false,
  sortBy: 'none',
  topN: 0,
  trendline: false,
  movingAvg: 0,
  bins: 10,
};

/**
 * The starting spec for a result: what the model proposed if it names real
 * columns, otherwise the highest-ranked suggestion for the shape.
 */
export function defaultSpec(artifact: ArtifactData, title = ''): ChartSpec {
  const best = suggestions(artifact)[0];
  const spec: ChartSpec = {
    ...EMPTY_SPEC,
    title: artifact.chart?.title || title,
    ...(best?.patch ?? {}),
  };

  const c = artifact.chart;
  if (
    c &&
    c.type &&
    c.type !== 'none' &&
    artifact.columns.includes(c.x) &&
    artifact.columns.includes(c.y)
  ) {
    return { ...spec, type: c.type as ChartSpec['type'], x: c.x, y: [c.y], series: null };
  }
  return spec;
}
