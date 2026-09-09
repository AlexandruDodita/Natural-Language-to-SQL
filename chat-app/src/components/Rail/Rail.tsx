import type {
  Conversation,
  HistoryEntry,
  SchemaCatalog,
  SchemaTable,
} from '../../types';
import { SchemaExplorer } from './SchemaExplorer';
import { QueryHistory } from './QueryHistory';

interface RailProps {
  conversations: Conversation[];
  currentConversationId: string | null;
  onSelectConversation: (id: string) => void;
  onDeleteConversation: (id: string) => void;
  onNewChat: () => void;

  catalog: SchemaCatalog | null;
  schemaLoading: boolean;
  schemaError: string | null;
  retrieved: string[];
  onPickTable: (t: SchemaTable) => void;

  history: HistoryEntry[];
  onRerun: (entry: HistoryEntry) => void;
  onClearHistory: () => void;
  busy: boolean;
}

export function Rail({
  conversations,
  currentConversationId,
  onSelectConversation,
  onDeleteConversation,
  onNewChat,
  catalog,
  schemaLoading,
  schemaError,
  retrieved,
  onPickTable,
  history,
  onRerun,
  onClearHistory,
  busy,
}: RailProps) {
  return (
    <aside className="rail">
      <div className="rail-sec">
        <div className="rail-head">
          <span className="label">Conversations</span>
          <button className="btn btn-ghost btn-sm" onClick={onNewChat}>
            + New
          </button>
        </div>

        <div className="rail-list">
          {conversations.length === 0 ? (
            <p className="chart-note">No conversations yet.</p>
          ) : (
            conversations.map(c => {
              const last = c.messages[c.messages.length - 1];
              const outcome = last?.sqlMeta?.outcome;
              const pill =
                outcome === 'clarification'
                  ? 'needs input'
                  : outcome === 'blocked_by_policy'
                    ? 'blocked'
                    : outcome
                      ? outcome.replace(/_/g, ' ')
                      : `${c.messageCount ?? c.messages.length} msg`;
              return (
                <div key={c.id} style={{ position: 'relative' }}>
                  <button
                    className="thread"
                    aria-current={c.id === currentConversationId}
                    onClick={() => onSelectConversation(c.id)}
                  >
                    <span className="thread-title">{c.title}</span>
                    <span className="thread-meta">
                      <span className="pill">{pill}</span>
                      {c.lastMessage ? c.lastMessage.slice(0, 28) : ''}
                    </span>
                  </button>
                  <button
                    className="btn btn-ghost btn-sm"
                    style={{ position: 'absolute', right: 4, top: 6 }}
                    aria-label={`Delete ${c.title}`}
                    onClick={() => onDeleteConversation(c.id)}
                  >
                    ✕
                  </button>
                </div>
              );
            })
          )}
        </div>
      </div>

      <SchemaExplorer
        catalog={catalog}
        loading={schemaLoading}
        error={schemaError}
        retrieved={retrieved}
        onPick={onPickTable}
      />

      <QueryHistory entries={history} onRerun={onRerun} onClear={onClearHistory} busy={busy} />
    </aside>
  );
}
