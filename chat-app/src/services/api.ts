import type { Message } from '../types';

const RAG_URL = import.meta.env.VITE_RAG_URL || 'http://localhost:8100';

export interface StreamResponse {
  chunk: string;
  done: boolean;
}

export async function* streamChat(
  messages: Message[]
): AsyncGenerator<StreamResponse, void, undefined> {
  const body = {
    messages: messages.map(m => ({
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

      yield { chunk: data, done: false };
    }
  }

  yield { chunk: '', done: true };
}

export async function sendMessage(messages: Message[]): Promise<string> {
  let result = '';
  for await (const { chunk, done } of streamChat(messages)) {
    if (done) break;
    result += chunk;
  }
  return result;
}
