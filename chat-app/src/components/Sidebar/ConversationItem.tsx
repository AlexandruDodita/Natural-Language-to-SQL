import type { Conversation } from '../../types';

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
      <div className="truncate font-medium">
        {conversation.title}
      </div>
      <div className={`text-xs truncate mt-0.5 ${isActive ? 'text-white/50' : 'text-white/40'}`}>
        {preview}
      </div>
    </button>
  );
}
