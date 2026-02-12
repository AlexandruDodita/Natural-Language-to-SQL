import { useState, useRef, useEffect, type KeyboardEvent } from 'react';

interface ChatInputProps {
  onSendMessage: (content: string) => void;
  disabled: boolean;
}

export function ChatInput({ onSendMessage, disabled }: ChatInputProps) {
  const [input, setInput] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.overflowY = 'hidden';
      const newHeight = Math.min(textareaRef.current.scrollHeight, 200);
      textareaRef.current.style.height = `${newHeight}px`;

      // Only show scrollbar if content exceeds max height
      if (textareaRef.current.scrollHeight > 200) {
        textareaRef.current.style.overflowY = 'auto';
      }
    }
  }, [input]);

  const handleSend = () => {
    if (!input.trim() || disabled) return;

    onSendMessage(input);
    setInput('');

    // Reset textarea height
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex-shrink-0 bg-[#2d2d2d]">
      <div className="w-full px-4 py-6 flex justify-center">
        <div className="w-full max-w-3xl">
          <div className="relative bg-[#353535] border border-white/10 rounded-2xl shadow-sm hover:border-white/20 transition-all focus-within:border-white/30">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask me anything..."
              disabled={disabled}
              className="w-full bg-transparent rounded-2xl focus:outline-none resize-none disabled:opacity-50 text-[15px] leading-relaxed placeholder:text-white/30 text-white/90"
              rows={1}
              style={{
                minHeight: '52px',
                maxHeight: '200px',
                paddingLeft: '24px',
                paddingRight: '64px',
                paddingTop: '14px',
                paddingBottom: '14px'
              }}
            />

            <div className="absolute right-3 bottom-2">
              <button
                onClick={handleSend}
                disabled={!input.trim() || disabled}
                className="w-9 h-9 bg-white/10 hover:bg-white/20 disabled:bg-white/5 disabled:cursor-not-allowed text-white/70 hover:text-white/90 disabled:text-white/30 rounded-full transition-all flex items-center justify-center"
                aria-label="Send message"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12h14M12 5l7 7-7 7" />
                </svg>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
