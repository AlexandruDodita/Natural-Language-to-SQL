import {
  BarChart, Bar,
  LineChart, Line,
  PieChart, Pie, Cell,
  AreaChart, Area,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts';
import type { ArtifactData } from '../../types';

const COLORS = [
  '#6366f1', '#8b5cf6', '#a78bfa', '#c4b5fd',
  '#818cf8', '#7c3aed', '#5b21b6', '#4f46e5',
  '#4338ca', '#3730a3', '#60a5fa', '#3b82f6',
];

interface ArtifactChartProps {
  artifact: ArtifactData;
}

export function ArtifactChart({ artifact }: ArtifactChartProps) {
  const { columns, rows, chart } = artifact;
  if (!chart) return null;

  const xIdx = columns.indexOf(chart.x);
  const yIdx = columns.indexOf(chart.y);
  if (xIdx === -1 || yIdx === -1) {
    return <div className="text-white/50 text-sm">Chart columns not found in data.</div>;
  }

  const data = rows.map(row => ({
    [chart.x]: row[xIdx],
    [chart.y]: typeof row[yIdx] === 'string' ? parseFloat(row[yIdx] as string) || 0 : row[yIdx],
  }));

  const commonProps = {
    data,
    margin: { top: 8, right: 24, left: 8, bottom: 8 },
  };

  const axisStyle = { fontSize: 11, fill: 'rgba(255,255,255,0.5)' };
  const gridStroke = 'rgba(255,255,255,0.08)';

  switch (chart.type) {
    case 'bar':
      return (
        <ResponsiveContainer width="100%" height={360}>
          <BarChart {...commonProps}>
            <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} />
            <XAxis dataKey={chart.x} tick={axisStyle} />
            <YAxis tick={axisStyle} />
            <Tooltip contentStyle={{ background: '#1e1e1e', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, fontSize: 12 }} />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Bar dataKey={chart.y} fill="#6366f1" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      );

    case 'line':
      return (
        <ResponsiveContainer width="100%" height={360}>
          <LineChart {...commonProps}>
            <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} />
            <XAxis dataKey={chart.x} tick={axisStyle} />
            <YAxis tick={axisStyle} />
            <Tooltip contentStyle={{ background: '#1e1e1e', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, fontSize: 12 }} />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Line type="monotone" dataKey={chart.y} stroke="#6366f1" strokeWidth={2} dot={{ r: 3, fill: '#6366f1' }} />
          </LineChart>
        </ResponsiveContainer>
      );

    case 'pie':
      return (
        <ResponsiveContainer width="100%" height={360}>
          <PieChart>
            <Pie
              data={data}
              dataKey={chart.y}
              nameKey={chart.x}
              cx="50%"
              cy="50%"
              outerRadius={120}
              label={({ name, percent }) => `${name} ${((percent ?? 0) * 100).toFixed(0)}%`}
              labelLine={{ stroke: 'rgba(255,255,255,0.3)' }}
              fontSize={11}
            >
              {data.map((_, i) => (
                <Cell key={i} fill={COLORS[i % COLORS.length]} />
              ))}
            </Pie>
            <Tooltip contentStyle={{ background: '#1e1e1e', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, fontSize: 12 }} />
            <Legend wrapperStyle={{ fontSize: 12 }} />
          </PieChart>
        </ResponsiveContainer>
      );

    case 'area':
      return (
        <ResponsiveContainer width="100%" height={360}>
          <AreaChart {...commonProps}>
            <CartesianGrid strokeDasharray="3 3" stroke={gridStroke} />
            <XAxis dataKey={chart.x} tick={axisStyle} />
            <YAxis tick={axisStyle} />
            <Tooltip contentStyle={{ background: '#1e1e1e', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 8, fontSize: 12 }} />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Area type="monotone" dataKey={chart.y} stroke="#6366f1" fill="#6366f1" fillOpacity={0.2} />
          </AreaChart>
        </ResponsiveContainer>
      );

    default:
      return <div className="text-white/50 text-sm">Unsupported chart type: {chart.type}</div>;
  }
}
