import type { Conversation } from '../../types';

const DEBUG = import.meta.env.VITE_DEBUG === 'true';

interface ConversationItemProps {
  conversation: Conversation;
  isActive: boolean;
  onSelect: () => void;
}

export function ConversationItem({ conversation, isActive, onSelect }: ConversationItemProps) {
  const preview = conversation.lastMessage
    ? conversation.lastMessage.slice(0, 45)
    : conversation.messages.length > 0
    ? conversation.messages[conversation.messages.length - 1].content.slice(0, 45)
    : 'Empty conversation';

  return (
    <button
      onClick={onSelect}
      className={`w-full text-left px-2.5 py-2 rounded-md transition-colors group relative text-sm ${
        isActive
          ? 'bg-white/10 text-white/90'
          : 'text-white/60 hover:bg-white/5 hover:text-white/80'
      }`}
    >
      <div className="flex items-center gap-1 min-w-0">
        <span className="truncate font-medium flex-1">{conversation.title}</span>
        {DEBUG && (
          <span className="flex-shrink-0 text-[10px] font-mono text-yellow-500/60 ml-1">
            {conversation.id.slice(0, 8)}
          </span>
        )}
      </div>
      <div className={`text-xs truncate mt-0.5 ${isActive ? 'text-white/50' : 'text-white/40'}`}>
        {preview}
      </div>
    </button>
  );
}
