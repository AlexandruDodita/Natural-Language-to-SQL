import type { AttemptInfo, SqlMeta } from '../../types';
import { copy } from '../../lib/sql';

// ---------------------------------------------------------------------------
// Self-repair trail
// ---------------------------------------------------------------------------
export function RepairTrail({ attempts }: { attempts: AttemptInfo[] }) {
  const failed = attempts.filter(a => !a.ok);
  if (!failed.length) return null;
  const succeeded = attempts.some(a => a.ok);

  return (
    <details className="notice warn">
      <summary className="notice-head">
        <span>⟲</span>
        <span>
          {succeeded
            ? `Self-repaired after ${failed.length} failed attempt${failed.length === 1 ? '' : 's'}`
            : `${failed.length} attempt${failed.length === 1 ? '' : 's'} failed`}
        </span>
        <span className="muted mono" style={{ marginLeft: 'auto' }}>
          show trail
        </span>
      </summary>
      <div className="notice-body">
        <div className="trail">
          {attempts.map((a, i) => (
            <div className={`trail-step ${a.ok ? 'pass' : 'fail'}`} key={`${a.index}-${i}`}>
              <span className="n">{a.index + 1}</span>
              <div style={{ minWidth: 0, flex: 1 }}>
                <div className="mono muted">
                  {a.stage}
                  {a.ok ? ' · ok' : ' · failed'}
                </div>
                {a.sql && <pre>{a.sql}</pre>}
                {a.error && <div className="err">{a.error}</div>}
              </div>
            </div>
          ))}
        </div>
        <p className="chart-note">
          The verbatim database error is what the repair loop feeds back to the model
          (<span className="mono">pipeline.py</span>, execution-feedback repair).
        </p>
      </div>
    </details>
  );
}

// ---------------------------------------------------------------------------
// Policy refusal — deliberately not an error
// ---------------------------------------------------------------------------
interface PolicyBlockProps {
  meta: SqlMeta;
  disabled: boolean;
  onRetryAs: (role: string) => void;
  onAskVariant: (text: string) => void;
}

export function PolicyBlockCard({ meta, disabled, onRetryAs, onAskVariant }: PolicyBlockProps) {
  const policy = meta.policy;
  const reason = policy?.blocked_reason || meta.blocked || 'not authorised';
  const role = policy?.role || meta.role || 'unknown';
  const denied = policy?.denied_columns ?? [];

  return (
    <div className="notice danger" style={{ padding: 'var(--s3)' }}>
      <div className="notice-head" style={{ padding: 0, marginBottom: 'var(--s2)' }}>
        <span>⛔</span>
        <span>Refused by the access policy</span>
      </div>
      <div style={{ fontSize: 'var(--t-xs)', color: 'var(--text-2)' }}>
        <p style={{ marginBottom: 'var(--s2)' }}>{reason}</p>
        <dl className="kv" style={{ marginBottom: 'var(--s3)' }}>
          <dt>role</dt>
          <dd>{role}</dd>
          <dt>rule</dt>
          <dd>policy.yaml · roles.{role}</dd>
          {denied.length > 0 && (
            <>
              <dt>denied columns</dt>
              <dd>{denied.join(', ')}</dd>
            </>
          )}
          {policy?.denied_tables?.length ? (
            <>
              <dt>denied tables</dt>
              <dd>{policy.denied_tables.join(', ')}</dd>
            </>
          ) : null}
        </dl>
        <p className="chart-note" style={{ marginBottom: 'var(--s3)' }}>
          This refusal is terminal by design — the model is never invited to find a way around
          the rule, so retrying the same question as the same role will refuse again.
        </p>
        <div className="row-gap">
          {role !== 'manager' && (
            <button className="btn btn-sm" disabled={disabled} onClick={() => onRetryAs('manager')}>
              Retry as manager
            </button>
          )}
          <button
            className="btn btn-sm"
            disabled={disabled}
            onClick={() => onAskVariant('Ask the same question without the restricted column: ')}
          >
            Ask a permitted variant
          </button>
          <button
            className="btn btn-sm"
            onClick={() =>
              copy(
                `Access request — role ${role} was refused: ${reason}` +
                  (meta.request_id ? ` (request_id ${meta.request_id})` : ''),
              )
            }
          >
            Copy for an access request
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Everything else that is not "answered"
// ---------------------------------------------------------------------------
const ADVICE: Record<string, { title: string; body: string; retry: boolean }> = {
  validation_failed: {
    title: 'The generated query was rejected before it ran',
    body:
      'The validator refused the query (read-only, single statement, known tables, row cap). ' +
      'Rephrasing the question usually helps more than retrying it unchanged.',
    retry: false,
  },
  execution_failed: {
    title: 'The database rejected the query',
    body: 'The repair budget was exhausted. The verbatim error is in the trail above.',
    retry: true,
  },
  generation_failed: {
    title: 'The model could not produce a query',
    body: 'This is a language-model failure, not a data one. Retrying is reasonable.',
    retry: true,
  },
  no_sql: {
    title: 'Answered without a query',
    body: 'The question did not need data, so no SQL was generated and nothing was read.',
    retry: false,
  },
};

interface FailureProps {
  meta: SqlMeta;
  disabled: boolean;
  onRetry: () => void;
}

export function FailureCard({ meta, disabled, onRetry }: FailureProps) {
  const advice = meta.outcome ? ADVICE[meta.outcome] : undefined;
  if (!advice) return null;
  const neutral = meta.outcome === 'no_sql';

  return (
    <div className={`notice ${neutral ? '' : 'danger'}`} style={{ padding: 'var(--s3)' }}>
      <div className="notice-head" style={{ padding: 0, marginBottom: 4 }}>
        <span>{neutral ? 'ℹ' : '⚠'}</span>
        <span>{advice.title}</span>
      </div>
      <p style={{ fontSize: 'var(--t-xs)', color: 'var(--text-2)' }}>{advice.body}</p>
      {meta.blocked && !neutral && (
        <pre className="err-text" style={{ marginTop: 'var(--s2)' }}>
          {meta.blocked}
        </pre>
      )}
      {advice.retry && (
        <div className="row-gap" style={{ marginTop: 'var(--s3)' }}>
          <button className="btn btn-sm" disabled={disabled} onClick={onRetry}>
            Retry
          </button>
        </div>
      )}
    </div>
  );
}

export function TransportErrorCard({
  detail,
  disabled,
  onRetry,
}: {
  detail: string;
  disabled: boolean;
  onRetry: () => void;
}) {
  return (
    <div className="notice danger" style={{ padding: 'var(--s3)' }}>
      <div className="notice-head" style={{ padding: 0, marginBottom: 4 }}>
        <span>⚠</span>
        <span>The request never reached the pipeline</span>
      </div>
      <pre className="err-text">{detail}</pre>
      <p className="chart-note">
        No SQL was generated and nothing was read. Check that the RAG service is up, then retry.
      </p>
      <div className="row-gap" style={{ marginTop: 'var(--s3)' }}>
        <button className="btn btn-sm" disabled={disabled} onClick={onRetry}>
          Retry
        </button>
      </div>
    </div>
  );
}
