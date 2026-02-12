import type { Message } from '../../types';
import { MessageBubble } from './MessageBubble';
import { TypingIndicator } from './TypingIndicator';
import { useAutoScroll } from '../../hooks/useAutoScroll';

interface MessageListProps {
  messages: Message[];
  isStreaming: boolean;
}

export function MessageList({ messages, isStreaming }: MessageListProps) {
  const scrollRef = useAutoScroll<HTMLDivElement>(messages.length);

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
        <>
          <div>
            {messages.map(message => (
              <MessageBubble key={message.id} message={message} />
            ))}
          </div>
          {isStreaming && messages[messages.length - 1]?.role === 'user' && (
            <TypingIndicator />
          )}
        </>
      )}
    </div>
  );
}
