import type { Message } from '../../types';
import { useAutoScroll } from '../../hooks/useAutoScroll';
import { Turn } from './Turn';

interface StreamProps {
  messages: Message[];
  isStreaming: boolean;
  database: string | null;
  onOpenResult: (message: Message, tab?: 'chart' | 'table' | 'sql' | 'prov') => void;
  onAsk: (question: string) => void;
  onRetry: () => void;
  onRetryAs: (role: string) => void;
  onPrefill: (text: string) => void;
}

export function Stream({
  messages,
  isStreaming,
  database,
  onOpenResult,
  onAsk,
  onRetry,
  onRetryAs,
  onPrefill,
}: StreamProps) {
  // The last message grows chunk by chunk while streaming, so the length of the
  // conversation alone is not enough to follow it.
  const tail = messages[messages.length - 1];
  const scrollRef = useAutoScroll<HTMLDivElement>(
    `${messages.length}:${tail?.content.length ?? 0}:${tail?.artifact ? 1 : 0}`,
  );

  return (
    <section className="stream" ref={scrollRef}>
      {messages.length === 0 ? (
        <div className="empty">
          <h1>Ask about the data</h1>
          <p>
            {database
              ? `Connected to ${database}. The rail on the left lists every table and column the retriever can reach; the workbench on the right shows the query, the result and the trace behind each answer.`
              : 'The schema explorer in the rail lists the tables the retriever can reach.'}
          </p>
        </div>
      ) : (
        <div className="stream-inner">
          {messages.map(m => (
            <Turn
              key={m.id}
              message={m}
              isStreaming={isStreaming}
              onOpenResult={onOpenResult}
              onAsk={onAsk}
              onRetry={onRetry}
              onRetryAs={onRetryAs}
              onPrefill={onPrefill}
            />
          ))}
        </div>
      )}
    </section>
  );
}
