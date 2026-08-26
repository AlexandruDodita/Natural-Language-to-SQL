import type { Message, ArtifactData, QueryEngine } from '../../types';
import { MessageList } from './MessageList';
import { ChatInput } from '../Input/ChatInput';

interface ChatAreaProps {
  messages: Message[];
  isStreaming: boolean;
  onSendMessage: (content: string) => void;
  onRetry: () => void;
  onToggleSidebar: () => void;
  onOpenArtifact: (artifact: ArtifactData) => void;
  engine: QueryEngine;
  onEngineChange: (engine: QueryEngine) => void;
}

export function ChatArea({ messages, isStreaming, onSendMessage, onRetry, onToggleSidebar, onOpenArtifact, engine, onEngineChange }: ChatAreaProps) {
  return (
    <div className="flex-1 flex flex-col bg-[#2d2d2d] relative min-w-0">
      {/* Header and query-engine switcher */}
      <div className="flex items-center justify-between gap-3 px-4 py-3 border-b border-white/10 bg-[#2d2d2d] shrink-0">
        <div className="flex items-center gap-3 min-w-0">
          <button
            onClick={onToggleSidebar}
            className="md:hidden text-white/60 hover:text-white/90 transition-colors"
            aria-label="Toggle sidebar"
          >
            <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
          <div className="min-w-0">
            <h1 className="text-sm font-medium text-white/90">SQL Assistant</h1>
            <p className="hidden sm:block text-[11px] text-white/35 truncate">
              {engine === 'rag' ? 'Retrieved schema + validation + self-repair' : 'MCP tools + read-only query execution'}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-1 rounded-lg bg-black/20 p-1 border border-white/10" role="group" aria-label="Query engine">
          {(['rag', 'mcp'] as QueryEngine[]).map(option => (
            <button
              key={option}
              onClick={() => onEngineChange(option)}
              disabled={isStreaming}
              className={`px-2.5 py-1 text-[11px] font-medium rounded-md transition-colors disabled:opacity-50 ${
                engine === option ? 'bg-blue-600 text-white' : 'text-white/45 hover:text-white/80'
              }`}
            >
              {option.toUpperCase()}
            </button>
          ))}
        </div>
      </div>

      {/* Messages */}
      <MessageList messages={messages} isStreaming={isStreaming} onRetry={onRetry} onOpenArtifact={onOpenArtifact} />

      {/* Input */}
      <ChatInput onSendMessage={onSendMessage} disabled={isStreaming} />
    </div>
  );
}
