export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

export interface Conversation {
  id: string;
  title: string;
  messages: Message[];
  createdAt: Date;
  messageCount?: number;
  lastMessage?: string;
}

export interface ChatState {
  conversations: Conversation[];
  currentConversationId: string | null;
  isStreaming: boolean;
  isSidebarOpen: boolean;
}
