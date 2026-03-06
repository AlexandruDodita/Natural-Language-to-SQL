export interface SqlMeta {
  sql: string | null;
  row_count: number | null;
  duration_ms: number | null;
  blocked: string | null;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  sqlMeta?: SqlMeta;
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
