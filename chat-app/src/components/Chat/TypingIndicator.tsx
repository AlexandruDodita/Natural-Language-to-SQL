export function TypingIndicator() {
  return (
    <div className="w-full py-6 px-4 border-b border-white/5">
      <div className="max-w-3xl mx-auto">
        <div className="flex items-center gap-1">
          <span className="w-2 h-2 bg-white/40 rounded-full animate-bounce" style={{ animationDelay: '0ms', animationDuration: '1.4s' }} />
          <span className="w-2 h-2 bg-white/40 rounded-full animate-bounce" style={{ animationDelay: '200ms', animationDuration: '1.4s' }} />
          <span className="w-2 h-2 bg-white/40 rounded-full animate-bounce" style={{ animationDelay: '400ms', animationDuration: '1.4s' }} />
        </div>
      </div>
    </div>
  );
}
