import { useState, useCallback, useEffect } from 'react';
import type {
  ArtifactData,
  Conversation,
  HistoryEntry,
  Message,
  QueryEngine,
  SqlMeta,
  UserContext,
} from '../types';
import { streamChat } from '../services/api';
import { backendApi } from '../services/backend-api';

const HISTORY_KEY = 'nl2sql-history';
const HISTORY_MAX = 40;

function loadHistory(): HistoryEntry[] {
  try {
    const raw = localStorage.getItem(HISTORY_KEY);
    return raw ? (JSON.parse(raw) as HistoryEntry[]) : [];
  } catch {
    return [];
  }
}

function saveHistory(entries: HistoryEntry[]) {
  try {
    localStorage.setItem(HISTORY_KEY, JSON.stringify(entries.slice(0, HISTORY_MAX)));
  } catch {
    // storage unavailable (private window): history is a convenience, not state
  }
}

/**
 * A transport failure is not a pipeline outcome. `generation_failed` and the
 * rest arrive as a normal answer with a meta record; only a dead socket or a
 * non-200 lands here, and only here is "try again" the right advice.
 */
function transportMessage(error: unknown): string {
  const detail = error instanceof Error ? error.message : String(error);
  return `The request did not reach the pipeline: ${detail}`;
}

export function useChat() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [currentConversationId, setCurrentConversationId] = useState<string | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [history, setHistory] = useState<HistoryEntry[]>(loadHistory);

  const currentConversation = conversations.find(c => c.id === currentConversationId);

  useEffect(() => {
    const loadConversations = async () => {
      try {
        setConversations(await backendApi.getConversations());
      } catch (error) {
        console.error('Error loading conversations:', error);
      } finally {
        setIsLoading(false);
      }
    };
    loadConversations();
  }, []);

  const recordHistory = useCallback((entry: HistoryEntry) => {
    setHistory(prev => {
      const next = [entry, ...prev.filter(e => e.sql !== entry.sql)].slice(0, HISTORY_MAX);
      saveHistory(next);
      return next;
    });
  }, []);

  const clearHistory = useCallback(() => {
    setHistory([]);
    saveHistory([]);
  }, []);

  const createNewConversation = useCallback(async () => {
    const newConversation = await backendApi.createConversation({ title: 'New Chat' });
    setConversations(prev => [newConversation, ...prev]);
    setCurrentConversationId(newConversation.id);
    return newConversation.id;
  }, []);

  const updateConversationTitle = useCallback((conversationId: string, firstMessage: string) => {
    const title = firstMessage.slice(0, 50) + (firstMessage.length > 50 ? '...' : '');
    setConversations(prev =>
      prev.map(conv => (conv.id === conversationId ? { ...conv, title } : conv)),
    );
    // The title has to reach the database too, or every stored thread comes
    // back as "New Chat" and the rail becomes a list of identical rows.
    backendApi.renameConversation(conversationId, title).catch(error => {
      console.error('Error renaming conversation:', error);
    });
  }, []);

  const patchMessage = useCallback(
    (conversationId: string, messageId: string, patch: Partial<Message>) => {
      setConversations(prev =>
        prev.map(conv =>
          conv.id === conversationId
            ? {
                ...conv,
                messages: conv.messages.map(m => (m.id === messageId ? { ...m, ...patch } : m)),
              }
            : conv,
        ),
      );
    },
    [],
  );

  /** Shared by `sendMessage` and `retryLastMessage`. */
  const consume = useCallback(
    async (
      conversationId: string,
      assistantMessageId: string,
      messagesToSend: Message[],
      engine: QueryEngine,
      user: UserContext,
      question: string,
    ) => {
      let content = '';
      let meta: SqlMeta | undefined;
      let artifact: ArtifactData | undefined;

      for await (const chunk of streamChat(messagesToSend, engine, user)) {
        if (chunk.done) break;

        if (chunk.sqlMeta !== undefined) {
          meta = chunk.sqlMeta;
          patchMessage(conversationId, assistantMessageId, { sqlMeta: meta });
          continue;
        }
        if (chunk.artifact !== undefined) {
          artifact = chunk.artifact;
          patchMessage(conversationId, assistantMessageId, { artifact });
          continue;
        }

        content += chunk.chunk;
        patchMessage(conversationId, assistantMessageId, { content });
      }

      // A blocked or failed turn still carries the last attempted SQL; only a
      // query that actually ran is worth offering as a re-run.
      if (meta?.sql && meta.outcome === 'answered') {
        recordHistory({
          id: meta.request_id || assistantMessageId,
          question,
          sql: meta.sql,
          rowCount: meta.row_count,
          durationMs: meta.duration_ms,
          outcome: meta.outcome,
          role: meta.role || user.role,
          at: Date.now(),
        });
      }

      if (content || meta || artifact) {
        const saved = await backendApi.createMessage(conversationId, {
          role: 'assistant',
          content,
          sql_meta: meta
            ? {
                sql_query: meta.sql ?? null,
                row_count: meta.row_count ?? null,
                duration_ms: meta.duration_ms ?? null,
                blocked: meta.blocked ?? null,
              }
            : null,
          artifact:
            artifact || meta ? { payload: artifact ?? null, meta: meta ?? null } : null,
        });
        // Swap the placeholder UUID for the DB-assigned id.
        patchMessage(conversationId, assistantMessageId, { id: saved.id });
      }
    },
    [patchMessage, recordHistory],
  );

  const sendMessage = useCallback(
    async (content: string, engine: QueryEngine, user: UserContext) => {
      if (!content.trim() || isStreaming) return;

      let conversationId = currentConversationId;
      const assistantMessageId = crypto.randomUUID();

      try {
        if (!conversationId) {
          conversationId = await createNewConversation();
        }

        const userMessage = await backendApi.createMessage(conversationId, {
          role: 'user',
          content: content.trim(),
        });

        setConversations(prev =>
          prev.map(conv =>
            conv.id === conversationId
              ? { ...conv, messages: [...conv.messages, userMessage] }
              : conv,
          ),
        );

        // `conversations` is a snapshot from before this render, so a thread
        // created a moment ago is not in it yet — that counts as empty.
        const conversation = conversations.find(c => c.id === conversationId);
        if (!conversation || conversation.messages.length === 0) {
          updateConversationTitle(conversationId, content.trim());
        }

        const assistantMessage: Message = {
          id: assistantMessageId,
          role: 'assistant',
          content: '',
          timestamp: new Date(),
        };
        setConversations(prev =>
          prev.map(conv =>
            conv.id === conversationId
              ? { ...conv, messages: [...conv.messages, assistantMessage] }
              : conv,
          ),
        );

        setIsStreaming(true);

        const messagesToSend = [...(conversation?.messages ?? []), userMessage];
        await consume(
          conversationId,
          assistantMessageId,
          messagesToSend,
          engine,
          user,
          content.trim(),
        );
      } catch (error) {
        console.error('Error sending message:', error);
        if (conversationId) {
          patchMessage(conversationId, assistantMessageId, {
            content: transportMessage(error),
            isError: true,
            transportError: error instanceof Error ? error.message : String(error),
          });
        }
      } finally {
        setIsStreaming(false);
      }
    },
    [
      currentConversationId,
      isStreaming,
      conversations,
      createNewConversation,
      updateConversationTitle,
      consume,
      patchMessage,
    ],
  );

  const retryLastMessage = useCallback(
    async (engine: QueryEngine, user: UserContext) => {
      if (!currentConversationId || isStreaming) return;

      const conversation = conversations.find(c => c.id === currentConversationId);
      if (!conversation || conversation.messages.length === 0) return;

      const messages = conversation.messages;
      let lastUserMsgIdx = -1;
      for (let i = messages.length - 1; i >= 0; i--) {
        if (messages[i].role === 'user') {
          lastUserMsgIdx = i;
          break;
        }
      }
      if (lastUserMsgIdx === -1) return;

      for (const msg of messages.slice(lastUserMsgIdx + 1)) {
        try {
          await backendApi.deleteMessage(currentConversationId, msg.id);
        } catch (e) {
          console.error('Error deleting message for retry:', e);
        }
      }

      const assistantMessageId = crypto.randomUUID();
      const messagesToSend = messages.slice(0, lastUserMsgIdx + 1);

      setConversations(prev =>
        prev.map(conv =>
          conv.id === currentConversationId
            ? {
                ...conv,
                messages: [
                  ...messagesToSend,
                  {
                    id: assistantMessageId,
                    role: 'assistant' as const,
                    content: '',
                    timestamp: new Date(),
                  },
                ],
              }
            : conv,
        ),
      );
      setIsStreaming(true);

      try {
        await consume(
          currentConversationId,
          assistantMessageId,
          messagesToSend,
          engine,
          user,
          messages[lastUserMsgIdx].content,
        );
      } catch (error) {
        console.error('Error retrying message:', error);
        patchMessage(currentConversationId, assistantMessageId, {
          content: transportMessage(error),
          isError: true,
          transportError: error instanceof Error ? error.message : String(error),
        });
      } finally {
        setIsStreaming(false);
      }
    },
    [currentConversationId, isStreaming, conversations, consume, patchMessage],
  );

  const selectConversation = useCallback(async (conversationId: string) => {
    setCurrentConversationId(conversationId);
    try {
      const conversation = await backendApi.getConversation(conversationId);
      setConversations(prev =>
        prev.map(conv =>
          conv.id === conversationId ? { ...conv, messages: conversation.messages } : conv,
        ),
      );
    } catch (error) {
      console.error('Error loading conversation messages:', error);
    }
  }, []);

  const deleteConversation = useCallback(
    async (conversationId: string) => {
      try {
        await backendApi.deleteConversation(conversationId);
        setConversations(prev => prev.filter(c => c.id !== conversationId));
        if (currentConversationId === conversationId) setCurrentConversationId(null);
      } catch (error) {
        console.error('Error deleting conversation:', error);
      }
    },
    [currentConversationId],
  );

  const startNewConversation = useCallback(() => {
    // Nothing is written until the first message: an empty thread in the rail
    // is noise.
    setCurrentConversationId(null);
  }, []);

  return {
    conversations,
    currentConversation,
    currentConversationId,
    isStreaming,
    isLoading,
    history,
    sendMessage,
    retryLastMessage,
    createNewConversation,
    startNewConversation,
    selectConversation,
    deleteConversation,
    clearHistory,
  };
}
