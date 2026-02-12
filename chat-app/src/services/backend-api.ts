import type { Conversation, Message } from '../types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

export interface ConversationSummary {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  user_id?: string;
}

export interface MessageCreate {
  role: 'user' | 'assistant';
  content: string;
}

export interface ConversationCreate {
  title: string;
  user_id?: string;
}

export const backendApi = {
  // Conversations
  async createConversation(data: ConversationCreate): Promise<Conversation> {
    const response = await fetch(`${API_BASE_URL}/conversations/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      throw new Error('Failed to create conversation');
    }

    const conversation = await response.json();
    return {
      id: conversation.id,
      title: conversation.title,
      createdAt: new Date(conversation.created_at),
      messages: (conversation.messages || []).map((msg: any) => ({
        id: msg.id,
        role: msg.role,
        content: msg.content,
        timestamp: new Date(msg.created_at),
      })),
    };
  },

  async getConversations(userId?: string): Promise<Conversation[]> {
    const url = new URL(`${API_BASE_URL}/conversations/`);
    if (userId) {
      url.searchParams.append('user_id', userId);
    }

    const response = await fetch(url.toString());

    if (!response.ok) {
      throw new Error('Failed to fetch conversations');
    }

    const conversations = await response.json();
    return conversations.map((conv: ConversationSummary) => ({
      id: conv.id,
      title: conv.title,
      createdAt: new Date(conv.created_at),
      messages: [],
    }));
  },

  async getConversation(conversationId: string): Promise<Conversation> {
    const response = await fetch(`${API_BASE_URL}/conversations/${conversationId}`);

    if (!response.ok) {
      throw new Error('Failed to fetch conversation');
    }

    const conversation = await response.json();
    return {
      id: conversation.id,
      title: conversation.title,
      createdAt: new Date(conversation.created_at),
      messages: (conversation.messages || []).map((msg: any) => ({
        id: msg.id,
        role: msg.role,
        content: msg.content,
        timestamp: new Date(msg.created_at),
      })),
    };
  },

  async deleteConversation(conversationId: string): Promise<void> {
    const response = await fetch(`${API_BASE_URL}/conversations/${conversationId}`, {
      method: 'DELETE',
    });

    if (!response.ok) {
      throw new Error('Failed to delete conversation');
    }
  },

  // Messages
  async createMessage(conversationId: string, message: MessageCreate): Promise<Message> {
    const response = await fetch(`${API_BASE_URL}/conversations/${conversationId}/messages/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(message),
    });

    if (!response.ok) {
      throw new Error('Failed to create message');
    }

    const msg = await response.json();
    return {
      id: msg.id,
      role: msg.role,
      content: msg.content,
      timestamp: new Date(msg.created_at),
    };
  },

  async getMessages(conversationId: string): Promise<Message[]> {
    const response = await fetch(`${API_BASE_URL}/conversations/${conversationId}/messages/`);

    if (!response.ok) {
      throw new Error('Failed to fetch messages');
    }

    const messages = await response.json();
    return messages.map((msg: any) => ({
      id: msg.id,
      role: msg.role,
      content: msg.content,
      timestamp: new Date(msg.created_at),
    }));
  },
};
