import type { ArtifactData, CellValue, ChartSpec } from '../types';
import { toNum } from './shape';

export interface SeriesData {
  /** Recharts rows: one object per x value. */
  data: Record<string, CellValue>[];
  /** The measure keys to draw, in order. */
  keys: string[];
  /** True when `spec.series` pivoted one measure into several columns. */
  pivoted: boolean;
  xKey: string;
}

const MA_SUFFIX = ' (moving avg)';
export const movingAvgKey = (k: string) => k + MA_SUFFIX;

/**
 * Turn a result set plus a spec into the row/key shape every chart draws from.
 * Sorting, top-N, series pivoting, 100% normalisation and the moving average all
 * happen here, so the chart components stay declarative.
 */
export function buildSeries(artifact: ArtifactData, spec: ChartSpec): SeriesData {
  const idx = (name: string) => artifact.columns.indexOf(name);
  const xKey = spec.x ?? '__index';
  const measures = spec.y.filter(y => idx(y) >= 0);

  let rows: Record<string, CellValue>[] = artifact.rows.map((row, i) => {
    const o: Record<string, CellValue> = {};
    artifact.columns.forEach((c, ci) => {
      o[c] = row[ci];
    });
    o.__index = i;
    return o;
  });

  let keys: string[] = measures;
  let pivoted = false;

  // One measure split by a category → one column per category value.
  if (spec.series && idx(spec.series) >= 0 && measures.length === 1 && spec.x) {
    const measure = measures[0];
    const byX = new Map<string, Record<string, CellValue>>();
    const seen: string[] = [];
    for (const r of rows) {
      const xv = String(r[spec.x] ?? '');
      const sv = String(r[spec.series] ?? '');
      if (!byX.has(xv)) byX.set(xv, { [spec.x]: r[spec.x] });
      const bucket = byX.get(xv)!;
      const prev = toNum(bucket[sv] ?? null) ?? 0;
      bucket[sv] = prev + (toNum(r[measure]) ?? 0);
      if (!seen.includes(sv)) seen.push(sv);
    }
    rows = [...byX.values()];
    keys = seen;
    pivoted = true;
  }

  // Sorting and top-N operate on the first measure.
  const primary = keys[0];
  if (primary && spec.sortBy !== 'none') {
    const dir = spec.sortBy === 'asc' ? 1 : -1;
    rows = [...rows].sort((a, b) => ((toNum(a[primary]) ?? 0) - (toNum(b[primary]) ?? 0)) * dir);
  }
  if (spec.topN > 0 && rows.length > spec.topN) {
    const ranked = primary
      ? [...rows].sort((a, b) => (toNum(b[primary]) ?? 0) - (toNum(a[primary]) ?? 0))
      : rows;
    const keep = new Set(ranked.slice(0, spec.topN));
    rows = rows.filter(r => keep.has(r));
  }

  // Numbers arrive as strings from psycopg; coerce once, here.
  rows = rows.map(r => {
    const o = { ...r };
    for (const k of keys) o[k] = toNum(r[k] ?? null);
    return o;
  });

  if (spec.normalize && keys.length > 1) {
    rows = rows.map(r => {
      const total = keys.reduce((a, k) => a + Math.abs((r[k] as number) ?? 0), 0) || 1;
      const o = { ...r };
      for (const k of keys) o[k] = (((r[k] as number) ?? 0) / total) * 100;
      return o;
    });
  }

  if (spec.movingAvg > 1 && primary) {
    const w = spec.movingAvg;
    rows = rows.map((r, i, all) => {
      const slice = all.slice(Math.max(0, i - w + 1), i + 1);
      const vals = slice.map(s => (s[primary] as number) ?? 0);
      return { ...r, [movingAvgKey(primary)]: vals.reduce((a, b) => a + b, 0) / vals.length };
    });
  }

  return { data: rows, keys, pivoted, xKey };
}

/** Equal-width bins over one numeric column. */
export function histogram(artifact: ArtifactData, column: string, bins: number) {
  const i = artifact.columns.indexOf(column);
  const values = artifact.rows.map(r => toNum(r[i])).filter((v): v is number => v !== null);
  if (!values.length) return { data: [] as Record<string, number | string>[], key: column };
  const min = Math.min(...values);
  const max = Math.max(...values);
  const n = Math.max(2, Math.min(60, bins || 10));
  const width = (max - min) / n || 1;
  const counts = new Array(n).fill(0);
  for (const v of values) {
    counts[Math.min(n - 1, Math.floor((v - min) / width))] += 1;
  }
  return {
    data: counts.map((c, b) => ({
      bin: `${Math.round((min + b * width) * 100) / 100}`,
      count: c,
    })),
    key: 'count',
  };
}

/** Ordinary least squares, used for the scatter trendline. */
export function linearFit(points: { x: number; y: number }[]) {
  const n = points.length;
  if (n < 2) return null;
  const sx = points.reduce((a, p) => a + p.x, 0);
  const sy = points.reduce((a, p) => a + p.y, 0);
  const sxx = points.reduce((a, p) => a + p.x * p.x, 0);
  const sxy = points.reduce((a, p) => a + p.x * p.y, 0);
  const denom = n * sxx - sx * sx;
  if (!denom) return null;
  const slope = (n * sxy - sx * sy) / denom;
  const intercept = (sy - slope * sx) / n;
  const xs = points.map(p => p.x);
  return { slope, intercept, minX: Math.min(...xs), maxX: Math.max(...xs) };
}
