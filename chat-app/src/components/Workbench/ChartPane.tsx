import { useMemo, useState } from 'react';
import type { ArtifactData, ChartSpec, ChartType } from '../../types';
import { CV } from '../../lib/format';
import { buildSeries } from '../../lib/series';
import { isNumeric, profile, shapeLine, suggestions } from '../../lib/shape';
import { ChartView } from './ChartView';

interface ChartPaneProps {
  artifact: ArtifactData;
  spec: ChartSpec;
  onSpecChange: (patch: Partial<ChartSpec>) => void;
}

const TYPES: ChartType[] = [
  'bar', 'hbar', 'line', 'area', 'pie', 'scatter', 'hist', 'combo', 'heat', 'facet', 'kpi', 'none',
];

export function ChartPane({ artifact, spec, onSpecChange }: ChartPaneProps) {
  const [hidden, setHidden] = useState<Record<string, boolean>>({});
  const p = useMemo(() => profile(artifact), [artifact]);
  const sugg = useMemo(() => suggestions(artifact), [artifact]);
  const built = useMemo(() => buildSeries(artifact, spec), [artifact, spec]);

  const numericCols = artifact.columns.filter((_, i) => isNumeric(p.kinds[i]));
  const active = (s: (typeof sugg)[number]) =>
    s.type === spec.type &&
    (s.patch.x ?? null) === spec.x &&
    JSON.stringify(s.patch.y ?? []) === JSON.stringify(spec.y);

  const toggleMeasure = (col: string) => {
    const next = spec.y.includes(col) ? spec.y.filter(c => c !== col) : [...spec.y, col];
    onSpecChange({ y: next });
  };

  return (
    <>
      {/* ranked suggestions for this result shape */}
      <div className="suggest">
        <span className="shape">{shapeLine(p)}</span>
        {sugg.map((s, i) => (
          <button
            key={`${s.type}-${s.label}-${i}`}
            className="sg"
            aria-pressed={active(s)}
            onClick={() => onSpecChange(s.patch)}
            title={s.why}
          >
            {s.label} <span className="why">· {s.why}</span>
          </button>
        ))}
      </div>

      {/* the spec, editable */}
      <div className="ctlbar">
        <div className="ctlgrp">
          <span>Type</span>
          <select
            className="ctl"
            value={spec.type}
            onChange={e => onSpecChange({ type: e.target.value as ChartType })}
          >
            {TYPES.map(t => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </div>

        <div className="ctlgrp">
          <span>X</span>
          <select
            className="ctl"
            value={spec.x ?? ''}
            onChange={e => onSpecChange({ x: e.target.value || null })}
          >
            <option value="">(row index)</option>
            {artifact.columns.map(c => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </div>

        <div className="ctlgrp">
          <span>Y</span>
          {numericCols.length === 0 && <span className="chart-note">no numeric column</span>}
          {numericCols.map(c => (
            <button
              key={c}
              className="sg"
              aria-pressed={spec.y.includes(c)}
              onClick={() => toggleMeasure(c)}
            >
              {c}
            </button>
          ))}
        </div>

        <div className="ctlgrp">
          <span>Split by</span>
          <select
            className="ctl"
            value={spec.series ?? ''}
            onChange={e => onSpecChange({ series: e.target.value || null })}
          >
            <option value="">none</option>
            {artifact.columns.map(c => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </div>

        {spec.type === 'combo' && (
          <div className="ctlgrp">
            <span>Right axis</span>
            <select
              className="ctl"
              value={spec.secondary ?? ''}
              onChange={e => onSpecChange({ secondary: e.target.value || null })}
            >
              <option value="">none</option>
              {numericCols.map(c => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </div>
        )}

        <label className="toggle">
          <input
            type="checkbox"
            checked={spec.stacked}
            onChange={e => onSpecChange({ stacked: e.target.checked })}
          />
          Stacked
        </label>
        <label className="toggle">
          <input
            type="checkbox"
            checked={spec.normalize}
            onChange={e => onSpecChange({ normalize: e.target.checked })}
          />
          100%
        </label>
        <label className="toggle">
          <input
            type="checkbox"
            checked={spec.trendline}
            onChange={e => onSpecChange({ trendline: e.target.checked })}
          />
          Trendline
        </label>

        <div className="ctlgrp">
          <span>Sort</span>
          <select
            className="ctl"
            value={spec.sortBy}
            onChange={e => onSpecChange({ sortBy: e.target.value as ChartSpec['sortBy'] })}
          >
            <option value="none">source order</option>
            <option value="desc">high → low</option>
            <option value="asc">low → high</option>
          </select>
        </div>

        <div className="ctlgrp">
          <span>Top N</span>
          <input
            className="ctl"
            style={{ width: 62 }}
            type="number"
            min={0}
            max={artifact.rows.length}
            value={spec.topN}
            onChange={e => onSpecChange({ topN: Number(e.target.value) || 0 })}
          />
        </div>

        <div className="ctlgrp">
          <span>Mov avg</span>
          <input
            className="ctl"
            style={{ width: 56 }}
            type="number"
            min={0}
            max={24}
            value={spec.movingAvg}
            onChange={e => onSpecChange({ movingAvg: Number(e.target.value) || 0 })}
          />
        </div>

        {spec.type === 'hist' && (
          <div className="ctlgrp">
            <span>Bins</span>
            <input
              className="ctl"
              style={{ width: 56 }}
              type="number"
              min={2}
              max={60}
              value={spec.bins}
              onChange={e => onSpecChange({ bins: Number(e.target.value) || 10 })}
            />
          </div>
        )}
      </div>

      <div className="chartbox">
        <ChartView artifact={artifact} spec={spec} hidden={hidden} />
        {built.keys.length > 1 && (
          <div className="legend">
            {built.keys.map((k, i) => (
              <button
                key={k}
                aria-pressed={!hidden[k]}
                onClick={() => setHidden(h => ({ ...h, [k]: !h[k] }))}
              >
                <span className="sw" style={{ background: CV(i) }} />
                {k}
              </button>
            ))}
          </div>
        )}
      </div>

      <p className="chart-note">
        The chart is drawn from one spec — type, x, measures, split-by, stacking, sort, top-N and
        the moving average are all fields of it. Marks use <span className="mono">var(--cN)</span>,
        so switching the theme re-colours the chart without a re-render.
      </p>
    </>
  );
}
