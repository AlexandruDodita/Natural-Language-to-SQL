import type {
  ArtifactData,
  ExecuteResult,
  Message,
  QueryEngine,
  RolePolicyInfo,
  SchemaCatalog,
  SqlMeta,
  UserContext,
} from '../types';

const RAG_URL = import.meta.env.VITE_RAG_URL || 'http://localhost:8100';
const MCP_URL = import.meta.env.VITE_MCP_URL || 'http://localhost:8300';

export interface StreamResponse {
  chunk: string;
  done: boolean;
  sqlMeta?: SqlMeta;
  artifact?: ArtifactData;
}

/** The user context travels with every request, so the role selector is real. */
function userPayload(user: UserContext) {
  return {
    user_id: user.user_id ?? undefined,
    role: user.role,
    location_id: user.location_id ?? undefined,
  };
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

  // The MCP arm has no pipeline stages to report; the outcome is derived so the
  // provenance strip reads the same way for both arms.
  const sqlMeta: SqlMeta = {
    sql: payload.final_sql ?? null,
    row_count: payload.final_sql ? payload.row_count ?? 0 : null,
    duration_ms: payload.final_sql ? payload.latency_ms ?? null : null,
    blocked: payload.error ?? null,
    outcome: payload.error ? 'execution_failed' : payload.final_sql ? 'answered' : 'no_sql',
    attempts: payload.attempts ?? undefined,
    engine: 'mcp',
    total_ms: payload.latency_ms ?? undefined,
  };
  yield { chunk: '', done: false, sqlMeta };

  if (payload.columns?.length) {
    yield {
      chunk: '',
      done: false,
      artifact: {
        columns: payload.columns,
        rows: payload.rows || [],
        chart: payload.chart ?? null,
        row_count: payload.row_count ?? (payload.rows || []).length,
      },
    };
  }

  if (payload.answer_text) {
    yield { chunk: payload.answer_text, done: false };
  }
  yield { chunk: '', done: true };
}

export async function* streamChat(
  messages: Message[],
  engine: QueryEngine,
  user: UserContext,
): AsyncGenerator<StreamResponse, void, undefined> {
  if (engine === 'mcp') {
    yield* streamMcp(messages);
    return;
  }

  const body = {
    messages: messages
      .filter(m => m.content.trim() !== '')
      .map(m => ({ role: m.role, content: m.content })),
    user: userPayload(user),
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
          const sqlMeta: SqlMeta = { ...JSON.parse(data.slice(6)), engine: 'rag' };
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

// ---------------------------------------------------------------------------
// The introspection endpoints the pipeline already exposed and the frontend
// never called.
// ---------------------------------------------------------------------------
async function getJson<T>(path: string): Promise<T> {
  const r = await fetch(`${RAG_URL}${path}`);
  if (!r.ok) throw new Error(`${path} → ${r.status}`);
  return r.json() as Promise<T>;
}

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(`${RAG_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!r.ok) {
    const detail = await r.text().catch(() => '');
    throw new Error(detail || `${path} → ${r.status}`);
  }
  return r.json() as Promise<T>;
}

export const ragApi = {
  schema: () => getJson<SchemaCatalog>('/schema'),

  roles: () => getJson<{ default: string; roles: RolePolicyInfo[] }>('/roles'),

  health: () => getJson<Record<string, unknown>>('/health'),

  config: () =>
    getJson<{ knobs: Record<string, unknown>; settings: Record<string, unknown> }>('/config'),

  retrieve: (question: string, topK?: number) =>
    postJson<{ mode: string; tables: string[]; ranking: unknown[] }>('/retrieve', {
      question,
      top_k: topK,
    }),

  /** Run user-edited SQL. Same validator and policy rewrite as a generated query. */
  execute: (sql: string, user: UserContext) =>
    postJson<ExecuteResult>('/execute', { sql, user: userPayload(user) }),

  explain: (sql: string, user: UserContext) =>
    postJson<ExecuteResult>('/execute', { sql, user: userPayload(user), explain: true }),

  async report(artifact: ArtifactData, title: string): Promise<Blob> {
    const r = await fetch(`${RAG_URL}/report`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        columns: artifact.columns,
        rows: artifact.rows,
        chart: artifact.chart,
        title,
      }),
    });
    if (!r.ok) throw new Error('Report generation failed');
    return r.blob();
  },
};
