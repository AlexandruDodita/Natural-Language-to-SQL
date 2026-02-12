import { useState } from 'react';
import { Sidebar } from '../Sidebar/Sidebar';
import { ChatArea } from '../Chat/ChatArea';
import { useChat } from '../../hooks/useChat';

export function AppLayout() {
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const {
    conversations,
    currentConversation,
    currentConversationId,
    isStreaming,
    sendMessage,
    createNewConversation,
    selectConversation,
  } = useChat();

  const handleNewChat = () => {
    createNewConversation();
    // Don't close sidebar on desktop, only on mobile
    if (window.innerWidth < 768) {
      setIsSidebarOpen(false);
    }
  };

  const handleSelectConversation = (id: string) => {
    selectConversation(id);
    // Close sidebar only on mobile when selecting conversation
    if (window.innerWidth < 768) {
      setIsSidebarOpen(false);
    }
  };

  const handleToggleSidebar = () => {
    setIsSidebarOpen(prev => !prev);
  };

  return (
    <div className="flex h-screen overflow-hidden bg-[#2d2d2d]">
      <Sidebar
        conversations={conversations}
        currentConversationId={currentConversationId}
        onNewChat={handleNewChat}
        onSelectConversation={handleSelectConversation}
        isOpen={isSidebarOpen}
        onClose={() => setIsSidebarOpen(false)}
        onToggle={handleToggleSidebar}
      />

      <ChatArea
        messages={currentConversation?.messages || []}
        isStreaming={isStreaming}
        onSendMessage={sendMessage}
        onToggleSidebar={handleToggleSidebar}
      />
    </div>
  );
}
