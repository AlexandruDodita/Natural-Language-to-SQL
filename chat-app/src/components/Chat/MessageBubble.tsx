import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import type { Message } from '../../types';

interface MessageBubbleProps {
  message: Message;
}

interface CodeBlockProps {
  children: string;
  className?: string;
}

function CodeBlock({ children, className }: CodeBlockProps) {
  const [copied, setCopied] = useState(false);
  const language = className?.replace('language-', '') || '';

  const handleCopy = async () => {
    await navigator.clipboard.writeText(children);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="relative group my-3">
      <div className="flex items-center justify-between px-3 py-1.5 bg-[#1a1a1a] border-b border-white/5 rounded-t-md">
        <span className="text-[11px] text-white/40 font-medium">
          {language || 'code'}
        </span>
        <button
          onClick={handleCopy}
          className="px-2 py-0.5 text-[11px] text-white/60 hover:text-white/90 transition-colors"
          aria-label="Copy code"
        >
          {copied ? 'Copied!' : 'Copy'}
        </button>
      </div>
      <pre className={`!mt-0 !rounded-t-none ${language === 'sql' ? 'language-sql' : ''}`}>
        <code className={className}>{children}</code>
      </pre>
    </div>
  );
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === 'user';

  return (
    <div className="w-full px-4 py-4 flex justify-center">
      <div className="w-full max-w-3xl">
        <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
          <div
            className={`max-w-[85%] ${isUser ? 'bg-[#404040] rounded-2xl rounded-br-md' : 'bg-[#353535] rounded-2xl rounded-bl-md'} shadow-lg border ${isUser ? 'border-white/10' : 'border-white/5'}`}
            style={{
              paddingLeft: isUser ? '24px' : '28px',
              paddingRight: isUser ? '24px' : '28px',
              paddingTop: '8px',
              paddingBottom: '8px'
            }}
          >
            {isUser ? (
              <p className="text-[15px] text-white/90 leading-relaxed whitespace-pre-wrap">{message.content}</p>
            ) : (
              <div className="markdown-content">
                <ReactMarkdown
                  components={{
                    code: ({ node, className, children, ...props }) => {
                      const content = String(children).replace(/\n$/, '');
                      const isInline = !className;

                      if (isInline) {
                        return (
                          <code className={className} {...props}>
                            {children}
                          </code>
                        );
                      }

                      return (
                        <CodeBlock className={className}>
                          {content}
                        </CodeBlock>
                      );
                    },
                  }}
                >
                  {message.content}
                </ReactMarkdown>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
