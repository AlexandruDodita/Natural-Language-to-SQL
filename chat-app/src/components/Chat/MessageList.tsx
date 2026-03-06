import type { Message } from '../../types';
import { MessageBubble } from './MessageBubble';
import { TypingIndicator } from './TypingIndicator';
import { useAutoScroll } from '../../hooks/useAutoScroll';

interface MessageListProps {
  messages: Message[];
  isStreaming: boolean;
  onRetry: () => void;
}

export function MessageList({ messages, isStreaming, onRetry }: MessageListProps) {
  const scrollRef = useAutoScroll<HTMLDivElement>(messages.length);

  // Find the index of the last user message for the retry button
  let lastUserMsgIdx = -1;
  for (let i = messages.length - 1; i >= 0; i--) {
    if (messages[i].role === 'user') { lastUserMsgIdx = i; break; }
  }

  return (
    <div
      ref={scrollRef}
      className="flex-1 overflow-y-auto"
    >
      {messages.length === 0 ? (
        <div className="flex flex-col items-center justify-center h-full px-4">
          <div className="max-w-2xl w-full text-center space-y-4 py-12">
            <h1 className="text-3xl font-normal text-white/90">
              How can I help you today?
            </h1>
            <p className="text-white/50 text-base">
              Ask me anything about SQL, databases, or data queries
            </p>
          </div>
        </div>
      ) : (
        <div className="flex flex-col gap-5 pt-5 pb-4">
          {messages.map((message, idx) => (
            <MessageBubble
              key={message.id}
              message={message}
              isLastUserMessage={idx === lastUserMsgIdx}
              isStreaming={isStreaming}
              onRetry={onRetry}
            />
          ))}
          {isStreaming && messages[messages.length - 1]?.role === 'user' && (
            <TypingIndicator />
          )}
        </div>
      )}
    </div>
  );
}
