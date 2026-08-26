import type { Message, SqlMeta, ArtifactData, QueryEngine } from '../types';

const RAG_URL = import.meta.env.VITE_RAG_URL || 'http://localhost:8100';
const MCP_URL = import.meta.env.VITE_MCP_URL || 'http://localhost:8300';

export interface StreamResponse {
  chunk: string;
  done: boolean;
  sqlMeta?: SqlMeta;
  artifact?: ArtifactData;
}

async function* streamMcp(messages: Message[]): AsyncGenerator<StreamResponse, void, undefined> {
  const question = [...messages].reverse().find(m => m.role === 'user')?.content.trim();
  if (!question) throw new Error('No user question provided');

  const response = await fetch(`${MCP_URL}/ask`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
  });

  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.error || `MCP gateway error: ${response.status}`);
  }
  if (payload.error && !payload.answer_text) {
    throw new Error(payload.error);
  }

  const sqlMeta: SqlMeta = {
    sql: payload.final_sql ?? null,
    row_count: payload.final_sql ? payload.row_count ?? 0 : null,
    duration_ms: payload.final_sql ? payload.latency_ms ?? null : null,
    blocked: payload.error ?? null,
  };
  yield { chunk: '', done: false, sqlMeta };

  if (payload.columns?.length) {
    yield {
      chunk: '',
      done: false,
      artifact: { columns: payload.columns, rows: payload.rows || [], chart: payload.chart ?? null },
    };
  }

  if (payload.answer_text) {
    yield { chunk: payload.answer_text, done: false };
  }
  yield { chunk: '', done: true };
}

export async function* streamChat(
  messages: Message[],
  engine: QueryEngine = 'rag',
): AsyncGenerator<StreamResponse, void, undefined> {
  if (engine === 'mcp') {
    yield* streamMcp(messages);
    return;
  }

  const body = {
    messages: messages
      .filter(m => m.content.trim() !== '')
      .map(m => ({
        role: m.role,
        content: m.content,
      })),
  };

  const response = await fetch(`${RAG_URL}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const err = await response.text();
    throw new Error(`RAG service error: ${err}`);
  }

  const reader = response.body?.getReader();
  if (!reader) throw new Error('No response body');

  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });

    // Parse SSE lines
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    for (const line of lines) {
      if (!line.startsWith('data: ')) continue;
      const data = line.slice(6);

      if (data === '[DONE]') {
        yield { chunk: '', done: true };
        return;
      }

      if (data.startsWith('[ERROR]')) {
        throw new Error(data.slice(8));
      }

      if (data.startsWith('[META]')) {
        try {
          const sqlMeta: SqlMeta = JSON.parse(data.slice(6));
          yield { chunk: '', done: false, sqlMeta };
        } catch {
          // malformed meta — ignore
        }
        continue;
      }

      if (data.startsWith('[DATA]')) {
        try {
          const artifact: ArtifactData = JSON.parse(data.slice(6));
          yield { chunk: '', done: false, artifact };
        } catch {
          // malformed data — ignore
        }
        continue;
      }

      try {
        yield { chunk: JSON.parse(data), done: false };
      } catch {
        yield { chunk: data, done: false };
      }
    }
  }

  yield { chunk: '', done: true };
}

export async function sendMessage(messages: Message[], engine: QueryEngine = 'rag'): Promise<string> {
  let result = '';
  for await (const { chunk, done } of streamChat(messages, engine)) {
    if (done) break;
    result += chunk;
  }
  return result;
}
