import type { Conversation } from '../../types';
import { ConversationItem } from './ConversationItem';

interface SidebarProps {
  conversations: Conversation[];
  currentConversationId: string | null;
  onNewChat: () => void;
  onSelectConversation: (id: string) => void;
  isOpen: boolean;
  onClose: () => void;
  onToggle: () => void;
}

export function Sidebar({
  conversations,
  currentConversationId,
  onNewChat,
  onSelectConversation,
  isOpen,
  onClose,
  onToggle,
}: SidebarProps) {
  const hasConversations = conversations.length > 0;
  const isInNewChat = !currentConversationId || (currentConversationId && conversations.find(c => c.id === currentConversationId)?.messages.length === 0);

  return (
    <>
      {/* Mobile overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/70 z-40 md:hidden"
          onClick={onClose}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`fixed md:relative inset-y-0 left-0 z-50 bg-[#232323] border-r border-white/5 flex flex-col transition-all duration-300 ${
          isOpen ? 'w-[260px]' : 'w-0 md:w-0'
        } ${isOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}`}
      >
        <div className={`${isOpen ? 'opacity-100' : 'opacity-0 md:opacity-0'} transition-opacity duration-300 flex flex-col h-full overflow-hidden`}>
          {/* Header */}
          <div className="flex-shrink-0 px-3 py-4 border-b border-white/5">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2 text-sm font-medium text-white/90">
                SQL Assistant
              </div>
              <button
                onClick={onToggle}
                className="text-white/60 hover:text-white/90 transition-colors p-1"
                aria-label="Close sidebar"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* Only show new chat button if not already in a new chat */}
            {!isInNewChat && (
              <button
                onClick={onNewChat}
                className="w-full px-3 py-2 bg-white/10 hover:bg-white/[0.15] text-white/90 rounded-md font-medium text-sm transition-colors flex items-center justify-center gap-2"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                </svg>
                New chat
              </button>
            )}
          </div>

          {/* Conversations list */}
          <div className="flex-1 overflow-y-auto px-2 py-2">
            {!hasConversations ? (
              <div className="text-center text-white/30 text-xs mt-8 px-4">
                No conversations yet
              </div>
            ) : (
              <div className="space-y-1">
                {conversations.map(conversation => (
                  <ConversationItem
                    key={conversation.id}
                    conversation={conversation}
                    isActive={conversation.id === currentConversationId}
                    onSelect={() => onSelectConversation(conversation.id)}
                  />
                ))}
              </div>
            )}
          </div>
        </div>
      </aside>

      {/* Sidebar toggle button - shows when sidebar is closed */}
      {!isOpen && (
        <button
          onClick={onToggle}
          className="hidden md:flex fixed top-4 left-4 z-30 w-8 h-8 items-center justify-center bg-[#2d2d2d] border border-white/10 rounded-lg shadow-lg hover:bg-[#353535] transition-all text-white/60 hover:text-white/90"
          aria-label="Open sidebar"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>
      )}
    </>
  );
}
