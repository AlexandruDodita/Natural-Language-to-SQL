import { useState } from 'react';
import { Sidebar } from '../Sidebar/Sidebar';
import { ChatArea } from '../Chat/ChatArea';
import { ArtifactPanel } from '../Artifact/ArtifactPanel';
import { useChat } from '../../hooks/useChat';
import type { ArtifactData } from '../../types';

export function AppLayout() {
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [openArtifact, setOpenArtifact] = useState<ArtifactData | null>(null);
  const {
    conversations,
    currentConversation,
    currentConversationId,
    isStreaming,
    sendMessage,
    retryLastMessage,
    createNewConversation,
    selectConversation,
  } = useChat();

  const handleNewChat = () => {
    createNewConversation();
    if (window.innerWidth < 768) {
      setIsSidebarOpen(false);
    }
  };

  const handleSelectConversation = (id: string) => {
    selectConversation(id);
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
        onRetry={retryLastMessage}
        onToggleSidebar={handleToggleSidebar}
        onOpenArtifact={setOpenArtifact}
      />

      {openArtifact && (
        <div className="w-[480px] shrink-0 h-full hidden md:block">
          <ArtifactPanel artifact={openArtifact} onClose={() => setOpenArtifact(null)} />
        </div>
      )}
    </div>
  );
}
