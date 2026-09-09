import ReactMarkdown from 'react-markdown';
import type { Message } from '../../types';
import { ProvenanceStrip } from './ProvenanceStrip';
import { ClarificationCard } from './ClarificationCard';
import { FailureCard, PolicyBlockCard, RepairTrail, TransportErrorCard } from './Notices';
import { ResultCard } from './ResultCard';

interface TurnProps {
  message: Message;
  isStreaming: boolean;
  onOpenResult: (message: Message, tab?: 'chart' | 'table' | 'sql' | 'prov') => void;
  onAsk: (question: string) => void;
  onRetry: () => void;
  onRetryAs: (role: string) => void;
  onPrefill: (text: string) => void;
}

export function Turn({
  message,
  isStreaming,
  onOpenResult,
  onAsk,
  onRetry,
  onRetryAs,
  onPrefill,
}: TurnProps) {
  if (message.role === 'user') {
    return (
      <div className="turn turn-user">
        <div className="bubble-user">{message.content}</div>
      </div>
    );
  }

  const meta = message.sqlMeta;
  const outcome = meta?.outcome;
  const attempts = meta?.attempts_detail ?? [];
  const hasArtifact = !!message.artifact && message.artifact.columns.length > 0;
  const isClarification = outcome === 'clarification';
  const pending = message.content === '' && !meta && isStreaming;

  return (
    <div className="turn">
      <div className="answer">
        {pending && (
          <div className="dots">
            <i />
            <i />
            <i />
          </div>
        )}

        {/* The clarification card carries the prose, so it is not printed twice. */}
        {!isClarification && message.content && !message.transportError && (
          <div className="prose">
            <ReactMarkdown>{message.content}</ReactMarkdown>
          </div>
        )}

        {message.transportError && (
          <TransportErrorCard detail={message.transportError} disabled={isStreaming} onRetry={onRetry} />
        )}

        {isClarification && meta && (
          <ClarificationCard
            meta={meta}
            prose={message.content}
            disabled={isStreaming}
            onChoose={onAsk}
          />
        )}

        {/* A policy refusal is recorded as a failed attempt, but nothing was
            repaired and nothing will be — the block card says so instead. */}
        {outcome !== 'blocked_by_policy' && attempts.some(a => !a.ok) && (
          <RepairTrail attempts={attempts} />
        )}

        {outcome === 'blocked_by_policy' && meta && (
          <PolicyBlockCard
            meta={meta}
            disabled={isStreaming}
            onRetryAs={onRetryAs}
            onAskVariant={onPrefill}
          />
        )}

        {meta && outcome && !['answered', 'clarification', 'blocked_by_policy'].includes(outcome) && (
          <FailureCard meta={meta} disabled={isStreaming} onRetry={onRetry} />
        )}

        {hasArtifact && (
          <ResultCard
            artifact={message.artifact!}
            title={meta?.request_id ? `Result ${meta.request_id.slice(0, 6)}` : 'Query result'}
            onOpen={() => onOpenResult(message)}
          />
        )}

        {meta && (
          <ProvenanceStrip
            meta={meta}
            onOpenTrace={() => onOpenResult(message, 'prov')}
            onOpenSql={() => onOpenResult(message, 'sql')}
          />
        )}
      </div>
    </div>
  );
}
