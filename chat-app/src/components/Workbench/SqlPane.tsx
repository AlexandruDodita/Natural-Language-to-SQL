import { useState } from 'react';
import type { ExecuteResult } from '../../types';
import { copy, formatSql } from '../../lib/sql';

interface SqlPaneProps {
  sql: string;
  generatedSql: string | null;
  role: string;
  maxRows: number | null | undefined;
  onRun: (sql: string) => Promise<ExecuteResult | null>;
  onExplain: (sql: string) => Promise<ExecuteResult | null>;
  busy: boolean;
}

/** Mounted with a `key` per result, so switching results resets the editor and
 *  running an edited query keeps what the user typed. */
export function SqlPane({ sql, generatedSql, role, maxRows, onRun, onExplain, busy }: SqlPaneProps) {
  const [text, setText] = useState(sql);
  const [copied, setCopied] = useState(false);
  const [plan, setPlan] = useState<string[] | null>(null);
  const [error, setError] = useState<{ stage: string | null; message: string } | null>(null);

  const edited = generatedSql !== null && text.trim() !== generatedSql.trim();

  const run = async () => {
    setError(null);
    setPlan(null);
    const result = await onRun(text);
    if (result && !result.ok) setError({ stage: result.stage, message: result.error ?? 'failed' });
  };

  const explain = async () => {
    setError(null);
    const result = await onExplain(text);
    if (!result) return;
    if (result.ok) setPlan(result.plan);
    else setError({ stage: result.stage, message: result.error ?? 'failed' });
  };

  return (
    <>
      <div className="sqlbar">
        <button className="btn btn-primary btn-sm" onClick={run} disabled={busy || !text.trim()}>
          ▶ Run
        </button>
        <button className="btn btn-sm" onClick={explain} disabled={busy || !text.trim()}>
          Explain
        </button>
        <button className="btn btn-sm" onClick={() => setText(t => formatSql(t))} disabled={!text.trim()}>
          Format
        </button>
        <button
          className="btn btn-sm"
          onClick={async () => {
            if (await copy(text)) {
              setCopied(true);
              setTimeout(() => setCopied(false), 1600);
            }
          }}
        >
          {copied ? 'Copied' : 'Copy'}
        </button>
        <div style={{ flex: 1 }} />
        {edited && (
          <span className="chip chip-warn">
            <span className="dot" />
            edited
          </span>
        )}
        <button
          className="btn btn-sm"
          disabled={!edited || generatedSql === null}
          onClick={() => setText(generatedSql ?? '')}
        >
          Revert to generated
        </button>
      </div>

      <div className={`sqlbox${edited ? ' edited' : ''}`}>
        <textarea value={text} spellCheck={false} onChange={e => setText(e.target.value)} />
      </div>

      <p className="chart-note">
        Running an edited query goes through the same validator and the same policy rewrite as a
        generated one (<span className="mono">POST /execute</span> → <span className="mono">Pipeline.run_sql</span>),
        under role <span className="mono">{role}</span>
        {maxRows ? <> with <span className="mono">max_rows = {maxRows}</span></> : null}. Editing
        cannot widen what the role may read.
      </p>

      {error && (
        <div className="notice danger" style={{ padding: 'var(--s3)', marginTop: 'var(--s3)' }}>
          <div className="notice-head" style={{ padding: 0, marginBottom: 4 }}>
            <span>⚠</span>
            <span>rejected at {error.stage ?? 'execution'}</span>
          </div>
          <pre className="err-text">{error.message}</pre>
        </div>
      )}

      {plan && (
        <div className="explain">
          <span className="label">Query plan</span>
          {plan.map((row, i) => (
            <div className="explain-row" key={i}>
              <span>{row}</span>
            </div>
          ))}
          {plan.length === 0 && <p className="chart-note">EXPLAIN returned no rows.</p>}
        </div>
      )}
    </>
  );
}
