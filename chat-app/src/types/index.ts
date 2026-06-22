export interface SqlMeta {
  sql: string | null;
  row_count: number | null;
  duration_ms: number | null;
  blocked: string | null;
}

export interface ChartConfig {
  type: 'bar' | 'line' | 'pie' | 'area';
  title: string;
  x: string;
  y: string;
}

export interface ArtifactData {
  columns: string[];
  rows: (string | number | null)[][];
  chart: ChartConfig | null;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  sqlMeta?: SqlMeta;
  artifact?: ArtifactData;
  isError?: boolean;
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
