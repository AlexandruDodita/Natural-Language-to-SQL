import { useState, useCallback, useEffect } from 'react';
import type { Message, Conversation } from '../types';
import { streamChat } from '../services/api';
import { backendApi } from '../services/backend-api';

export function useChat() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [currentConversationId, setCurrentConversationId] = useState<string | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  const currentConversation = conversations.find(c => c.id === currentConversationId);

  // Load conversations from backend on mount
  useEffect(() => {
    const loadConversations = async () => {
      try {
        const data = await backendApi.getConversations();
        setConversations(data);
      } catch (error) {
        console.error('Error loading conversations:', error);
      } finally {
        setIsLoading(false);
      }
    };

    loadConversations();
  }, []);

  const createNewConversation = useCallback(async () => {
    try {
      const newConversation = await backendApi.createConversation({ title: 'New Chat' });
      setConversations(prev => [newConversation, ...prev]);
      setCurrentConversationId(newConversation.id);
      return newConversation.id;
    } catch (error) {
      console.error('Error creating conversation:', error);
      throw error;
    }
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

      try {
        // Create a new conversation if none exists
        if (!conversationId) {
          conversationId = await createNewConversation();
        }

        // Save user message to backend
        const userMessage = await backendApi.createMessage(conversationId, {
          role: 'user',
          content: content.trim(),
        });

        // Add user message to local state
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

          // Update assistant message content in local state
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

        // Save assistant message to backend after streaming is complete
        if (accumulatedContent) {
          await backendApi.createMessage(conversationId, {
            role: 'assistant',
            content: accumulatedContent,
          });
        }
      } catch (error) {
        console.error('Error sending message:', error);

        const errorContent = 'Sorry, there was an error processing your request. Please try again.';

        // Update assistant message with error in local state
        setConversations(prev =>
          prev.map(conv =>
            conv.id === conversationId
              ? {
                  ...conv,
                  messages: conv.messages.map(msg =>
                    msg.id === assistantMessageId
                      ? { ...msg, content: errorContent }
                      : msg
                  ),
                }
              : conv
          )
        );

        // Try to save error message to backend
        try {
          await backendApi.createMessage(conversationId, {
            role: 'assistant',
            content: errorContent,
          });
        } catch (backendError) {
          console.error('Error saving error message to backend:', backendError);
        }
      } finally {
        setIsStreaming(false);
      }
    },
    [currentConversationId, isStreaming, conversations, createNewConversation, updateConversationTitle]
  );

  const selectConversation = useCallback(async (conversationId: string) => {
    setCurrentConversationId(conversationId);

    // Load messages for the selected conversation
    try {
      const conversation = await backendApi.getConversation(conversationId);
      setConversations(prev =>
        prev.map(conv =>
          conv.id === conversationId
            ? { ...conv, messages: conversation.messages }
            : conv
        )
      );
    } catch (error) {
      console.error('Error loading conversation messages:', error);
    }
  }, []);

  const deleteConversation = useCallback(async (conversationId: string) => {
    try {
      await backendApi.deleteConversation(conversationId);
      setConversations(prev => prev.filter(c => c.id !== conversationId));
      if (currentConversationId === conversationId) {
        setCurrentConversationId(null);
      }
    } catch (error) {
      console.error('Error deleting conversation:', error);
    }
  }, [currentConversationId]);

  return {
    conversations,
    currentConversation,
    currentConversationId,
    isStreaming,
    isLoading,
    sendMessage,
    createNewConversation,
    selectConversation,
    deleteConversation,
  };
}
