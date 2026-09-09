import { useEffect, useRef, type KeyboardEvent } from 'react';
import type { QueryEngine } from '../../types';

interface ComposerProps {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  disabled: boolean;
  engine: QueryEngine;
  role: string;
  maxRows: number | null;
  starters: string[];
  onStarter: (text: string) => void;
}

export function Composer({
  value,
  onChange,
  onSend,
  disabled,
  engine,
  role,
  maxRows,
  starters,
  onStarter,
}: ComposerProps) {
  const ref = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 180)}px`;
    el.style.overflowY = el.scrollHeight > 180 ? 'auto' : 'hidden';
  }, [value]);

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      onSend();
    }
  };

  return (
    <div className="composer">
      <div className="composer-inner">
        <div className="composer-box">
          <textarea
            ref={ref}
            rows={1}
            value={value}
            disabled={disabled}
            onChange={e => onChange(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Ask about the data — e.g. “revenue per branch by payment method in 2024”"
          />
          <div className="composer-bar">
            <span className="chip">
              <span className="dot" />
              {engine === 'rag' ? 'RAG pipeline' : 'MCP tools'}
            </span>
            <span className="chip">
              <span className="dot" />
              {role}
            </span>
            <span className="chip">
              <span className="dot" />
              read-only{maxRows ? ` · max ${maxRows} rows` : ''}
            </span>
            <div className="spacer" />
            <button className="send" onClick={onSend} disabled={disabled || !value.trim()} aria-label="Send">
              →
            </button>
          </div>
        </div>

        {starters.length > 0 && (
          <div className="starter-row">
            {starters.map(s => (
              <button key={s} className="starter" disabled={disabled} onClick={() => onStarter(s)}>
                {s}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
