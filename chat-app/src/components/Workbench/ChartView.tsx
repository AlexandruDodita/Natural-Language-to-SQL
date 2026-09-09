import { useMemo } from 'react';
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Line,
  LineChart,
  Pie,
  PieChart,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { ArtifactData, ChartSpec } from '../../types';
import { CV, fmtNum } from '../../lib/format';
import { buildSeries, histogram, linearFit, movingAvgKey } from '../../lib/series';
import { toNum } from '../../lib/shape';

interface ChartViewProps {
  artifact: ArtifactData;
  spec: ChartSpec;
  height?: number;
  compact?: boolean;
  hidden?: Record<string, boolean>;
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function Tip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="tip">
      <b>{String(label ?? payload[0]?.name ?? '')}</b>
      {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
      {payload.map((p: any, i: number) => (
        <div className="row" key={i}>
          <span className="sw" style={{ background: p.color || p.fill }} />
          <span>{p.name}</span>
          <span style={{ marginLeft: 'auto', fontWeight: 600 }}>{fmtNum(p.value)}</span>
        </div>
      ))}
    </div>
  );
}

const axisProps = {
  tick: { fontSize: 11 },
  tickLine: false,
  axisLine: { stroke: 'var(--border)' },
} as const;

const margin = { top: 8, right: 16, left: 4, bottom: 4 };

/**
 * One component for every chart type in the spec. The mockup drew these by hand
 * to show they all come from one declarative object; here recharts does the
 * drawing and the spec is still the interface.
 */
export function ChartView({ artifact, spec, height = 320, compact = false, hidden = {} }: ChartViewProps) {
  const built = useMemo(() => buildSeries(artifact, spec), [artifact, spec]);
  const keys = built.keys.filter(k => !hidden[k]);

  if (spec.type === 'none' || (!keys.length && spec.type !== 'hist' && spec.type !== 'kpi')) {
    return <p className="chart-note">No measure selected — the table tab has the full result.</p>;
  }

  // -- single scalar --------------------------------------------------------
  if (spec.type === 'kpi') {
    const key = spec.y[0];
    const value = built.data.length ? toNum(built.data[0][key] ?? null) : null;
    return (
      <div className="kpi-big">
        <span className="v">{fmtNum(value)}</span>
        <span className="k">{key}</span>
      </div>
    );
  }

  // -- distribution ---------------------------------------------------------
  if (spec.type === 'hist') {
    const { data } = histogram(artifact, spec.y[0] ?? '', spec.bins);
    return (
      <ResponsiveContainer width="100%" height={height}>
        <BarChart data={data} margin={margin}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="bin" {...axisProps} />
          <YAxis {...axisProps} tickFormatter={fmtNum} />
          <Tooltip content={<Tip />} cursor={{ fill: 'var(--surface-2)' }} />
          <Bar dataKey="count" fill={CV(0)} radius={[3, 3, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    );
  }

  // -- correlation ----------------------------------------------------------
  if (spec.type === 'scatter') {
    const xk = spec.x ?? '';
    const yk = keys[0];
    const points = built.data
      .map(r => ({ x: toNum(r[xk] ?? null) ?? 0, y: toNum(r[yk] ?? null) ?? 0 }))
      .filter(p => Number.isFinite(p.x) && Number.isFinite(p.y));
    const fit = spec.trendline ? linearFit(points) : null;

    return (
      <ResponsiveContainer width="100%" height={height}>
        <ScatterChart margin={margin}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis type="number" dataKey="x" name={xk} {...axisProps} tickFormatter={fmtNum} />
          <YAxis type="number" dataKey="y" name={yk} {...axisProps} tickFormatter={fmtNum} />
          <Tooltip content={<Tip />} cursor={{ strokeDasharray: '3 3' }} />
          <Scatter data={points} fill={CV(0)} name={`${xk} × ${yk}`} />
          {fit && (
            <ReferenceLine
              stroke={CV(3)}
              strokeDasharray="5 4"
              segment={[
                { x: fit.minX, y: fit.intercept + fit.slope * fit.minX },
                { x: fit.maxX, y: fit.intercept + fit.slope * fit.maxX },
              ]}
            />
          )}
        </ScatterChart>
      </ResponsiveContainer>
    );
  }

  // -- part of whole --------------------------------------------------------
  if (spec.type === 'pie') {
    const key = keys[0];
    return (
      <ResponsiveContainer width="100%" height={height}>
        <PieChart>
          <Pie
            data={built.data}
            dataKey={key}
            nameKey={built.xKey}
            cx="50%"
            cy="50%"
            innerRadius={compact ? 28 : 62}
            outerRadius={compact ? 52 : 110}
            paddingAngle={1}
            label={compact ? false : ({ name, percent }) => `${name} ${((percent ?? 0) * 100).toFixed(0)}%`}
            labelLine={false}
            fontSize={11}
          >
            {built.data.map((_, i) => (
              <Cell key={i} fill={CV(i)} stroke="var(--surface)" />
            ))}
          </Pie>
          <Tooltip content={<Tip />} />
        </PieChart>
      </ResponsiveContainer>
    );
  }

  // -- time × category matrix ----------------------------------------------
  if (spec.type === 'heat') {
    const values = built.data.flatMap(r => keys.map(k => (r[k] as number) ?? 0));
    const max = Math.max(1, ...values.map(Math.abs));
    return (
      <div className="heat-grid">
        <table className="heat">
          <thead>
            <tr>
              <th />
              {keys.map(k => (
                <th key={k}>{k}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {built.data.map((r, i) => (
              <tr key={i}>
                <th>{String(r[built.xKey] ?? '')}</th>
                {keys.map(k => {
                  const v = (r[k] as number) ?? 0;
                  return (
                    <td
                      key={k}
                      title={`${k}: ${fmtNum(v)}`}
                      style={{
                        background: CV(0),
                        opacity: 0.12 + 0.88 * (Math.abs(v) / max),
                      }}
                    />
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  // -- small multiples ------------------------------------------------------
  if (spec.type === 'facet') {
    return (
      <div className="facet-grid">
        {keys.map((k, i) => (
          <div className="facet" key={k}>
            <b>{k}</b>
            <ResponsiveContainer width="100%" height={Math.max(90, height / 3)}>
              <LineChart data={built.data} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
                <XAxis dataKey={built.xKey} hide />
                <YAxis hide />
                <Tooltip content={<Tip />} />
                <Line type="monotone" dataKey={k} stroke={CV(i)} strokeWidth={1.6} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        ))}
      </div>
    );
  }

  // -- horizontal bars ------------------------------------------------------
  if (spec.type === 'hbar') {
    return (
      <ResponsiveContainer width="100%" height={Math.max(height, built.data.length * 22 + 40)}>
        <BarChart data={built.data} layout="vertical" margin={{ ...margin, left: 24 }}>
          <CartesianGrid strokeDasharray="3 3" horizontal={false} />
          <XAxis type="number" {...axisProps} tickFormatter={fmtNum} />
          <YAxis type="category" dataKey={built.xKey} width={140} {...axisProps} />
          <Tooltip content={<Tip />} cursor={{ fill: 'var(--surface-2)' }} />
          {keys.map((k, i) => (
            <Bar
              key={k}
              dataKey={k}
              stackId={spec.stacked ? 'a' : undefined}
              fill={CV(i)}
              radius={[0, 3, 3, 0]}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
    );
  }

  // -- dual axis ------------------------------------------------------------
  if (spec.type === 'combo') {
    return (
      <ResponsiveContainer width="100%" height={height}>
        <ComposedChart data={built.data} margin={margin}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey={built.xKey} {...axisProps} />
          <YAxis yAxisId="left" {...axisProps} tickFormatter={fmtNum} />
          <YAxis yAxisId="right" orientation="right" {...axisProps} tickFormatter={fmtNum} />
          <Tooltip content={<Tip />} />
          {keys.map((k, i) => (
            <Bar key={k} yAxisId="left" dataKey={k} fill={CV(i)} radius={[3, 3, 0, 0]} />
          ))}
          {spec.secondary && (
            <Line
              yAxisId="right"
              type="monotone"
              dataKey={spec.secondary}
              stroke={CV(keys.length)}
              strokeWidth={2}
              dot={false}
            />
          )}
        </ComposedChart>
      </ResponsiveContainer>
    );
  }

  // -- area -----------------------------------------------------------------
  if (spec.type === 'area') {
    return (
      <ResponsiveContainer width="100%" height={height}>
        <AreaChart data={built.data} margin={margin}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey={built.xKey} {...axisProps} />
          <YAxis {...axisProps} tickFormatter={fmtNum} domain={spec.normalize ? [0, 100] : undefined} />
          <Tooltip content={<Tip />} />
          {keys.map((k, i) => (
            <Area
              key={k}
              type="monotone"
              dataKey={k}
              stackId={spec.stacked || spec.normalize ? 'a' : undefined}
              stroke={CV(i)}
              fill={CV(i)}
              fillOpacity={0.22}
              strokeWidth={1.8}
            />
          ))}
        </AreaChart>
      </ResponsiveContainer>
    );
  }

  // -- line -----------------------------------------------------------------
  if (spec.type === 'line') {
    const ma = spec.movingAvg > 1 && keys[0] ? movingAvgKey(keys[0]) : null;
    return (
      <ResponsiveContainer width="100%" height={height}>
        <LineChart data={built.data} margin={margin}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey={built.xKey} {...axisProps} />
          <YAxis {...axisProps} tickFormatter={fmtNum} />
          <Tooltip content={<Tip />} />
          {keys.map((k, i) => (
            <Line
              key={k}
              type="monotone"
              dataKey={k}
              stroke={CV(i)}
              strokeWidth={1.9}
              dot={built.data.length <= 24 && !compact ? { r: 2.5 } : false}
            />
          ))}
          {ma && (
            <Line
              type="monotone"
              dataKey={ma}
              stroke={CV(keys.length)}
              strokeDasharray="5 4"
              strokeWidth={1.6}
              dot={false}
            />
          )}
        </LineChart>
      </ResponsiveContainer>
    );
  }

  // -- bars (default) -------------------------------------------------------
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={built.data} margin={margin}>
        <CartesianGrid strokeDasharray="3 3" vertical={false} />
        <XAxis dataKey={built.xKey} {...axisProps} interval="preserveStartEnd" />
        <YAxis {...axisProps} tickFormatter={fmtNum} domain={spec.normalize ? [0, 100] : undefined} />
        <Tooltip content={<Tip />} cursor={{ fill: 'var(--surface-2)' }} />
        {keys.map((k, i) => (
          <Bar
            key={k}
            dataKey={k}
            stackId={spec.stacked || spec.normalize ? 'a' : undefined}
            fill={CV(i)}
            radius={[3, 3, 0, 0]}
          />
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}
