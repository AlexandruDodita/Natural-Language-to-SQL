import type { SqlMeta, Stage } from '../../types';
import { CV, OUTCOME_LABEL, OUTCOME_TONE, chipClass, fmtMs } from '../../lib/format';

interface ProvenancePaneProps {
  meta: SqlMeta | undefined;
  tableCount: number | null;
}

const STAGE_ORDER: Stage[] = ['retrieval', 'generation', 'validation', 'policy', 'dry_run', 'execution', 'answer'];

/**
 * Nothing here is measured for the panel's benefit: every field is already
 * written per request by `telemetry.RequestTrace`. The panel only surfaces it.
 */
export function ProvenancePane({ meta, tableCount }: ProvenancePaneProps) {
  if (!meta) {
    return <p className="chart-note">No trace for this result.</p>;
  }

  const stages = meta.stages ?? {};
  const present = STAGE_ORDER.filter(s => (stages[s] ?? 0) > 0);
  const total = present.reduce((a, s) => a + (stages[s] ?? 0), 0);

  const ranking = meta.retrieval?.ranking ?? [];
  const top = ranking.length ? Math.max(...ranking.map(r => r.score)) || 1 : 1;
  const used = new Set((meta.retrieval?.tables ?? []).map(t => t.toLowerCase()));
  const policy = meta.policy;
  const outcome = meta.outcome;

  return (
    <>
      <div className="pv-sec">
        <span className="label">Outcome</span>
        <div className="row-gap">
          <span className={chipClass(outcome ? OUTCOME_TONE[outcome] : 'neutral')}>
            <span className="dot" />
            {outcome ? OUTCOME_LABEL[outcome] : 'unknown'}
          </span>
          <span className="chip">
            <span className="dot" />
            {meta.engine === 'mcp' ? 'MCP tools' : 'RAG pipeline'}
          </span>
          {meta.model && (
            <span className="chip">
              <span className="dot" />
              {meta.model}
            </span>
          )}
          <span className="chip">
            <span className="dot" />
            role {meta.role ?? '—'}
          </span>
          {(meta.retries ?? 0) > 0 && (
            <span className="chip chip-warn">
              <span className="dot" />
              {meta.retries} repair{meta.retries === 1 ? '' : 's'}
            </span>
          )}
        </div>
      </div>

      {present.length > 0 && (
        <div className="pv-sec">
          <span className="label">Stage latency · {(total / 1000).toFixed(2)} s</span>
          <div className="stagebar">
            {present.map((s, i) => (
              <div
                key={s}
                style={{ width: `${(100 * (stages[s] ?? 0)) / total}%`, background: CV(i) }}
                title={`${s} ${fmtMs(stages[s] ?? 0)}`}
              >
                {(stages[s] ?? 0) / total > 0.09 ? `${Math.round(stages[s] ?? 0)} ms` : ''}
              </div>
            ))}
          </div>
          <div className="stagekey">
            {present.map((s, i) => (
              <span key={s}>
                <i style={{ background: CV(i) }} />
                {s} · {fmtMs(stages[s] ?? 0)}
              </span>
            ))}
          </div>
          <p className="chart-note">
            The answering stage is not included: the trace is sent before the model starts
            streaming the prose.
          </p>
        </div>
      )}

      <div className="pv-sec">
        <span className="label">
          Schema retrieval — mode {meta.retrieval?.mode ?? 'n/a'}, {(meta.retrieval?.tables ?? []).length} of{' '}
          {meta.retrieval?.candidates ?? tableCount ?? '?'} tables sent to the model
        </span>
        {ranking.length > 0 ? (
          <div className="rank">
            {ranking.map(r => (
              <div className="rank-row" key={r.table}>
                <span className={`nm${used.has(r.table.toLowerCase()) ? ' on' : ''}`}>{r.table}</span>
                <span className="bar">
                  <i style={{ width: `${(100 * r.score) / top}%` }} />
                </span>
                <span className="sc">{r.score.toFixed(2)}</span>
              </div>
            ))}
          </div>
        ) : (
          <p className="chart-note">
            Retrieval was disabled or ran in fallback mode — the whole schema was sent.
          </p>
        )}
        {meta.retrieval?.expanded?.length ? (
          <p className="chart-note">
            Foreign-key expansion added: <span className="mono">{meta.retrieval.expanded.join(', ')}</span>
          </p>
        ) : null}
        {meta.retrieval?.value_matches?.length ? (
          <p className="chart-note">
            Value index hits:{' '}
            {meta.retrieval.value_matches.map((v, i) => (
              <span className="mono" key={i}>
                {[v.table, v.column].filter(Boolean).join('.')}
                {v.value ? ` = ${v.value}` : ''}
                {i < (meta.retrieval?.value_matches?.length ?? 0) - 1 ? ', ' : ''}
              </span>
            ))}
          </p>
        ) : null}
      </div>

      <div className="pv-sec">
        <span className="label">Authorization</span>
        <dl className="kv">
          <dt>policy role</dt>
          <dd>{policy?.role ?? meta.role ?? '—'}</dd>
          <dt>enforcement</dt>
          <dd>{policy?.enabled === false ? 'disabled' : 'AST rewrite + RLS'}</dd>
          <dt>row filters</dt>
          <dd>
            {policy?.filter_predicates?.length
              ? policy.filter_predicates.map(f => f.predicate).join(' AND ')
              : policy?.filters?.length
                ? policy.filters.join(', ')
                : 'none applied'}
          </dd>
          <dt>denied columns</dt>
          <dd>{policy?.denied_columns?.length ? policy.denied_columns.join(', ') : 'none for this role'}</dd>
          {policy?.expanded_stars?.length ? (
            <>
              <dt>expanded SELECT *</dt>
              <dd>{policy.expanded_stars.join(', ')}</dd>
            </>
          ) : null}
          <dt>row cap</dt>
          <dd>max_rows = {policy?.max_rows ?? meta.max_rows ?? '—'}</dd>
          {policy?.blocked_reason ? (
            <>
              <dt>blocked</dt>
              <dd>{policy.blocked_reason}</dd>
            </>
          ) : null}
        </dl>
      </div>

      <div className="pv-sec">
        <span className="label">Telemetry record</span>
        <dl className="kv">
          <dt>request_id</dt>
          <dd>{meta.request_id ?? '—'}</dd>
          <dt>attempts</dt>
          <dd>{meta.attempts ?? '—'}</dd>
          <dt>row_count</dt>
          <dd>
            {meta.row_count ?? '—'}
            {meta.truncated ? ' (truncated)' : ''}
          </dd>
          <dt>database</dt>
          <dd>{meta.database ?? '—'}</dd>
          <dt>sink</dt>
          <dd>telemetry.jsonl</dd>
        </dl>
        <p className="chart-note">
          Every field here is already written per request by{' '}
          <span className="mono">telemetry.RequestTrace</span>; the panel only surfaces it.
        </p>
      </div>
    </>
  );
}
