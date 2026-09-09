import type { SqlMeta } from '../../types';
import { OUTCOME_LABEL, OUTCOME_TONE, chipClass, fmtMs } from '../../lib/format';

interface ProvenanceStripProps {
  meta: SqlMeta;
  onOpenTrace: () => void;
  onOpenSql: () => void;
}

/**
 * Always visible under an answer: what happened, how long it took, how many
 * attempts it needed, which tables it read and under which role. One click from
 * the full trace.
 */
export function ProvenanceStrip({ meta, onOpenTrace, onOpenSql }: ProvenanceStripProps) {
  const outcome = meta.outcome;
  const tone = outcome ? OUTCOME_TONE[outcome] : 'neutral';
  const tables = meta.retrieval?.tables ?? [];
  const attempts = meta.attempts ?? 0;

  return (
    <div className="prov">
      <span className={chipClass(tone)}>
        <span className="dot" />
        {outcome ? OUTCOME_LABEL[outcome] : meta.sql ? 'answered' : 'no query'}
      </span>

      {meta.row_count !== null && meta.row_count !== undefined && (
        <span className="chip">
          <span className="dot" />
          {meta.row_count} row{meta.row_count === 1 ? '' : 's'}
          {meta.truncated ? ' (capped)' : ''}
        </span>
      )}

      {meta.duration_ms !== null && meta.duration_ms !== undefined && (
        <span className="chip" title="SQL execution time · total pipeline time up to the answer">
          <span className="dot" />
          {fmtMs(meta.duration_ms)} sql
          {meta.total_ms ? ` · ${fmtMs(meta.total_ms)} total` : ''}
        </span>
      )}

      {attempts > 1 && (
        <span className="chip chip-warn">
          <span className="dot" />
          {attempts} attempts
        </span>
      )}

      {tables.length > 0 && (
        <span className="chip mono" title={tables.join(', ')}>
          <span className="dot" />
          {tables.slice(0, 3).join(', ')}
          {tables.length > 3 ? ` +${tables.length - 3}` : ''}
        </span>
      )}

      <span className="chip">
        <span className="dot" />
        role {meta.role ?? '—'}
      </span>

      <div className="prov-sep" />

      {meta.sql && (
        <button className="chip" onClick={onOpenSql}>
          SQL
        </button>
      )}
      <button className="chip" onClick={onOpenTrace}>
        Trace{meta.request_id ? ` ${meta.request_id.slice(0, 6)}` : ''}
      </button>
    </div>
  );
}
