import { useMemo } from 'react';
import type { ArtifactData } from '../../types';
import { defaultSpec } from '../../lib/shape';
import { ChartView } from '../Workbench/ChartView';

interface ResultCardProps {
  artifact: ArtifactData;
  title: string;
  onOpen: () => void;
}

export function ResultCard({ artifact, title, onOpen }: ResultCardProps) {
  const spec = useMemo(() => defaultSpec(artifact, title), [artifact, title]);
  const rows = artifact.rows.length;

  return (
    <div className="rescard">
      <button className="rescard-head" onClick={onOpen}>
        <span className="ico">▤</span>
        <span className="t">
          <b>{artifact.chart?.title || title || 'Query result'}</b>
          <span>
            {rows} row{rows === 1 ? '' : 's'} · {artifact.columns.length} column
            {artifact.columns.length === 1 ? '' : 's'}
            {spec.type !== 'none' ? ` · ${spec.type}` : ''}
            {artifact.truncated ? ' · capped' : ''}
          </span>
        </span>
        <span className="muted">Open ▸</span>
      </button>
      {spec.type !== 'none' && (
        <div className="rescard-preview">
          <ChartView artifact={artifact} spec={spec} height={140} compact />
        </div>
      )}
    </div>
  );
}
