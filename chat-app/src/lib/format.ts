import type { CellValue, Outcome } from '../types';

/** The eight-hue categorical ramp from the design system. */
export const CV = (i: number) => `var(--c${(i % 8) + 1})`;
export const CHART_HUES = 8;

export function fmtNum(v: unknown): string {
  if (v === null || v === undefined || v === '') return '—';
  const n = typeof v === 'number' ? v : Number(v);
  if (!Number.isFinite(n)) return String(v);
  const a = Math.abs(n);
  if (a >= 1e9) return `${(n / 1e9).toFixed(2)}B`;
  if (a >= 1e6) return `${(n / 1e6).toFixed(2)}M`;
  if (a >= 1e4) return `${(n / 1e3).toFixed(1)}k`;
  if (Number.isInteger(n)) return n.toLocaleString('en-US');
  return (Math.round(n * 100) / 100).toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

export function fmtCell(v: CellValue): string {
  if (v === null || v === undefined) return 'null';
  return String(v);
}

export function fmtMs(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return '—';
  if (ms >= 1000) return `${(ms / 1000).toFixed(2)} s`;
  return `${ms.toFixed(ms < 10 ? 1 : 0)} ms`;
}

export function fmtWhen(ts: number): string {
  const secs = Math.max(0, Math.round((Date.now() - ts) / 1000));
  if (secs < 45) return 'now';
  if (secs < 3600) return `${Math.round(secs / 60)} min`;
  if (secs < 86400) return `${Math.round(secs / 3600)} h`;
  return `${Math.round(secs / 86400)} d`;
}

/** Human labels for the closed outcome vocabulary of `telemetry.py`. */
export const OUTCOME_LABEL: Record<Outcome, string> = {
  answered: 'answered',
  no_sql: 'no query needed',
  clarification: 'needs a choice',
  blocked_by_policy: 'refused by policy',
  validation_failed: 'query rejected',
  execution_failed: 'query failed',
  generation_failed: 'model unavailable',
};

export type OutcomeTone = 'ok' | 'warn' | 'danger' | 'neutral';

export const OUTCOME_TONE: Record<Outcome, OutcomeTone> = {
  answered: 'ok',
  no_sql: 'neutral',
  clarification: 'warn',
  blocked_by_policy: 'danger',
  validation_failed: 'danger',
  execution_failed: 'danger',
  generation_failed: 'danger',
};

export const chipClass = (tone: OutcomeTone) =>
  tone === 'neutral' ? 'chip' : `chip chip-${tone}`;

export function truncate(s: string, n: number): string {
  return s.length > n ? `${s.slice(0, n - 1)}…` : s;
}
