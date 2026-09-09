import type { HistoryEntry } from '../../types';
import { fmtMs, fmtWhen, truncate } from '../../lib/format';

interface QueryHistoryProps {
  entries: HistoryEntry[];
  onRerun: (entry: HistoryEntry) => void;
  onClear: () => void;
  busy: boolean;
}

export function QueryHistory({ entries, onRerun, onClear, busy }: QueryHistoryProps) {
  return (
    <div className="rail-sec">
      <div className="rail-head">
        <span className="label">Query history</span>
        {entries.length > 0 && (
          <button className="btn btn-ghost btn-sm" onClick={onClear}>
            Clear
          </button>
        )}
      </div>

      {entries.length === 0 ? (
        <p className="chart-note">
          Answered queries land here. Re-running one replays the stored SQL — no model call.
        </p>
      ) : (
        <div className="hist">
          {entries.map(e => (
            <button
              key={`${e.id}-${e.at}`}
              className="hist-item"
              disabled={busy}
              onClick={() => onRerun(e)}
              title={e.sql}
            >
              <span className="htxt">
                <span className="hq">{truncate(e.question, 46)}</span>
                <span className="hm">
                  {e.rowCount ?? '—'} rows · {fmtMs(e.durationMs)} · {e.role} · {fmtWhen(e.at)}
                </span>
              </span>
              <span className="rerun">Re-run</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
