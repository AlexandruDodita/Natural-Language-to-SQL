import { useState } from 'react';
import type { SqlMeta } from '../../types';

interface ClarificationCardProps {
  meta: SqlMeta;
  prose: string;
  disabled: boolean;
  onChoose: (question: string) => void;
}

/**
 * The clarification turn, made actionable.
 *
 * `pipeline.py` already decides that a question is ambiguous and the model
 * already names the readings; rendering them as buttons means the user picks a
 * reading instead of re-typing the question, and the reading that was chosen is
 * recorded in the thread — so the query stays reproducible.
 */
export function ClarificationCard({ meta, prose, disabled, onChoose }: ClarificationCardProps) {
  const [free, setFree] = useState('');
  const options = meta.clarification_options ?? [];
  const keys = ['A', 'B', 'C', 'D', 'E'];

  return (
    <div className="clarify">
      <h4>{meta.clarification || 'Which reading did you mean?'}</h4>
      {prose && <p>{prose}</p>}

      {options.length > 0 ? (
        <div className="opts">
          {options.map((o, i) => (
            <button
              key={`${o.label}-${i}`}
              className="opt"
              disabled={disabled}
              onClick={() => onChoose(o.question || o.label)}
            >
              <span className="k">{keys[i] ?? i + 1}</span>
              <span className="b">
                <b>{o.label}</b>
                {o.measure && <span>{o.measure}</span>}
                {o.note && <span style={{ fontFamily: 'var(--font-sans)' }}>{o.note}</span>}
              </span>
            </button>
          ))}
        </div>
      ) : (
        <p className="chart-note">
          The model did not return structured readings for this question — answer in your own
          words below.
        </p>
      )}

      <div className="opt-free">
        <input
          className="ctl"
          value={free}
          placeholder="…or state the reading yourself"
          disabled={disabled}
          onChange={e => setFree(e.target.value)}
          onKeyDown={e => {
            if (e.key === 'Enter' && free.trim()) {
              onChoose(free.trim());
              setFree('');
            }
          }}
        />
        <button
          className="btn btn-sm"
          disabled={disabled || !free.trim()}
          onClick={() => {
            onChoose(free.trim());
            setFree('');
          }}
        >
          Send
        </button>
      </div>
    </div>
  );
}
