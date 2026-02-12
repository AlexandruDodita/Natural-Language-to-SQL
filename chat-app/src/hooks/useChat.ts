import { useState, useCallback } from 'react';
import type { Message, Conversation } from '../types';
import { streamChat } from '../services/api';

export function useChat() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [currentConversationId, setCurrentConversationId] = useState<string | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);

  const currentConversation = conversations.find(c => c.id === currentConversationId);

  const createNewConversation = useCallback(() => {
    const newConversation: Conversation = {
      id: crypto.randomUUID(),
      title: 'New Chat',
      messages: [],
      createdAt: new Date(),
    };

    setConversations(prev => [newConversation, ...prev]);
    setCurrentConversationId(newConversation.id);

    return newConversation.id;
  }, []);

  const updateConversationTitle = useCallback((conversationId: string, firstMessage: string) => {
    const title = firstMessage.slice(0, 50) + (firstMessage.length > 50 ? '...' : '');
    setConversations(prev =>
      prev.map(conv =>
        conv.id === conversationId ? { ...conv, title } : conv
      )
    );
  }, []);

  const sendMessage = useCallback(
    async (content: string) => {
      if (!content.trim() || isStreaming) return;

      let conversationId = currentConversationId;

      // Create a new conversation if none exists
      if (!conversationId) {
        conversationId = createNewConversation();
      }

      // Create user message
      const userMessage: Message = {
        id: crypto.randomUUID(),
        role: 'user',
        content: content.trim(),
        timestamp: new Date(),
      };

      // Add user message to conversation
      setConversations(prev =>
        prev.map(conv =>
          conv.id === conversationId
            ? { ...conv, messages: [...conv.messages, userMessage] }
            : conv
        )
      );

      // Update conversation title if it's the first message
      const conversation = conversations.find(c => c.id === conversationId);
      if (conversation && conversation.messages.length === 0) {
        updateConversationTitle(conversationId, content);
      }

      // Create assistant message placeholder
      const assistantMessageId = crypto.randomUUID();
      const assistantMessage: Message = {
        id: assistantMessageId,
        role: 'assistant',
        content: '',
        timestamp: new Date(),
      };

      // Add assistant message placeholder
      setConversations(prev =>
        prev.map(conv =>
          conv.id === conversationId
            ? { ...conv, messages: [...conv.messages, assistantMessage] }
            : conv
        )
      );

      setIsStreaming(true);

      try {
        // Get updated conversation messages for API call
        const updatedConversation = conversations.find(c => c.id === conversationId);
        const messagesToSend = updatedConversation
          ? [...updatedConversation.messages, userMessage]
          : [userMessage];

        let accumulatedContent = '';

        // Stream the response
        for await (const { chunk, done } of streamChat(messagesToSend)) {
          if (done) break;

          accumulatedContent += chunk;

          // Update assistant message content
          setConversations(prev =>
            prev.map(conv =>
              conv.id === conversationId
                ? {
                    ...conv,
                    messages: conv.messages.map(msg =>
                      msg.id === assistantMessageId
                        ? { ...msg, content: accumulatedContent }
                        : msg
                    ),
                  }
                : conv
            )
          );
        }
      } catch (error) {
        console.error('Error sending message:', error);

        // Update assistant message with error
        setConversations(prev =>
          prev.map(conv =>
            conv.id === conversationId
              ? {
                  ...conv,
                  messages: conv.messages.map(msg =>
                    msg.id === assistantMessageId
                      ? {
                          ...msg,
                          content: 'Sorry, there was an error processing your request. Please try again.',
                        }
                      : msg
                  ),
                }
              : conv
          )
        );
      } finally {
        setIsStreaming(false);
      }
    },
    [currentConversationId, isStreaming, conversations, createNewConversation, updateConversationTitle]
  );

  const selectConversation = useCallback((conversationId: string) => {
    setCurrentConversationId(conversationId);
  }, []);

  const deleteConversation = useCallback((conversationId: string) => {
    setConversations(prev => prev.filter(c => c.id !== conversationId));
    if (currentConversationId === conversationId) {
      setCurrentConversationId(null);
    }
  }, [currentConversationId]);

  return {
    conversations,
    currentConversation,
    currentConversationId,
    isStreaming,
    sendMessage,
    createNewConversation,
    selectConversation,
    deleteConversation,
  };
}
