import type { Message } from '../../types';
import { MessageList } from './MessageList';
import { ChatInput } from '../Input/ChatInput';

interface ChatAreaProps {
  messages: Message[];
  isStreaming: boolean;
  onSendMessage: (content: string) => void;
  onToggleSidebar: () => void;
}

export function ChatArea({ messages, isStreaming, onSendMessage, onToggleSidebar }: ChatAreaProps) {
  return (
    <div className="flex-1 flex flex-col bg-[#2d2d2d] relative">
      {/* Mobile header */}
      <div className="md:hidden flex items-center gap-3 px-4 py-3 border-b border-white/10 bg-[#2d2d2d]">
        <button
          onClick={onToggleSidebar}
          className="text-white/60 hover:text-white/90 transition-colors"
          aria-label="Toggle sidebar"
        >
          <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>
        <h1 className="text-sm font-medium text-white/90">SQL Assistant</h1>
      </div>

      {/* Messages */}
      <MessageList messages={messages} isStreaming={isStreaming} />

      {/* Input */}
      <ChatInput onSendMessage={onSendMessage} disabled={isStreaming} />
    </div>
  );
}
