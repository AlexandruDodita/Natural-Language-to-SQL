// ---------------------------------------------------------------------------
// The pipeline contract.
//
// `sql_meta` is what `rag-service/pipeline.py` puts on the `[META]` SSE frame.
// Everything below `blocked` is optional because the MCP arm and older stored
// messages carry only the four original fields.
// ---------------------------------------------------------------------------
export type Outcome =
  | 'answered'
  | 'no_sql'
  | 'clarification'
  | 'blocked_by_policy'
  | 'validation_failed'
  | 'execution_failed'
  | 'generation_failed';

export type Stage = 'retrieval' | 'generation' | 'validation' | 'policy' | 'dry_run' | 'execution' | 'answer';

export interface TableScore {
  table: string;
  score: number;
  dense: number;
  lexical: number;
  value: number;
}

export interface ValueMatch {
  table?: string;
  column?: string;
  value?: string;
  [key: string]: unknown;
}

export interface RetrievalInfo {
  mode: string | null;
  tables: string[];
  ranking?: TableScore[];
  value_matches?: ValueMatch[];
  expanded?: string[];
  latency_ms?: number | null;
  candidates?: number | null;
}

export interface PolicyFilter {
  table: string;
  alias?: string | null;
  predicate: string;
}

export interface PolicyInfo {
  role: string;
  enabled?: boolean;
  filters: string[];
  filter_predicates?: PolicyFilter[];
  expanded_stars?: string[];
  denied_columns?: string[];
  denied_tables?: string[];
  blocked_reason?: string | null;
  max_rows?: number | null;
}

export interface AttemptInfo {
  index: number;
  sql: string | null;
  stage: string;
  ok: boolean;
  error: string | null;
  duration_ms?: number;
}

export interface ClarificationOption {
  label: string;
  measure?: string | null;
  note?: string | null;
  /** The original question, restated so it names this reading. Sent verbatim. */
  question?: string | null;
}

export interface SqlMeta {
  sql: string | null;
  row_count: number | null;
  duration_ms: number | null;
  blocked: string | null;

  outcome?: Outcome;
  attempts?: number;
  retries?: number;
  request_id?: string;
  role?: string;
  model?: string;
  database?: string | null;
  max_rows?: number | null;
  truncated?: boolean;
  total_ms?: number;
  stages?: Partial<Record<Stage, number>>;
  attempts_detail?: AttemptInfo[];
  retrieval?: RetrievalInfo;
  policy?: PolicyInfo;
  clarification?: string | null;
  clarification_options?: ClarificationOption[];
  /** Set by the frontend, not the pipeline: which arm produced this turn. */
  engine?: QueryEngine;
}

// ---------------------------------------------------------------------------
// Results and charts
// ---------------------------------------------------------------------------
export type CellValue = string | number | boolean | null;

/** What the model proposes on the `[DATA]` frame. */
export interface ChartConfig {
  type: 'bar' | 'line' | 'pie' | 'area' | string;
  title: string;
  x: string;
  y: string;
}

export interface ArtifactData {
  columns: string[];
  rows: CellValue[][];
  chart: ChartConfig | null;
  truncated?: boolean;
  row_count?: number;
}

export type ChartType =
  | 'bar'
  | 'hbar'
  | 'line'
  | 'area'
  | 'pie'
  | 'scatter'
  | 'hist'
  | 'combo'
  | 'kpi'
  | 'facet'
  | 'heat'
  | 'none';

/**
 * One declarative spec drives every chart type — the point the mockup makes by
 * drawing all of them from the same object.
 */
export interface ChartSpec {
  type: ChartType;
  title: string;
  x: string | null;
  y: string[];
  series: string | null;
  secondary: string | null;
  stacked: boolean;
  normalize: boolean;
  sortBy: 'none' | 'asc' | 'desc';
  topN: number;
  trendline: boolean;
  movingAvg: number;
  bins: number;
}

export type ColumnKind = 'int' | 'num' | 'date' | 'month' | 'text' | 'bool';

export interface ChartSuggestion {
  rank: number;
  type: ChartType;
  label: string;
  why: string;
  patch: Partial<ChartSpec>;
}

// ---------------------------------------------------------------------------
// Conversation
// ---------------------------------------------------------------------------
export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  sqlMeta?: SqlMeta;
  artifact?: ArtifactData;
  isError?: boolean;
  /** Transport-level failure: distinct from a pipeline outcome. */
  transportError?: string;
}

export interface Conversation {
  id: string;
  title: string;
  messages: Message[];
  createdAt: Date;
  messageCount?: number;
  lastMessage?: string;
}

export type QueryEngine = 'rag' | 'mcp';

export interface UserContext {
  role: string;
  location_id?: number | null;
  user_id?: string | null;
}

// ---------------------------------------------------------------------------
// Schema catalog (`GET /schema`)
// ---------------------------------------------------------------------------
export interface SchemaColumn {
  name: string;
  data_type: string;
  nullable?: boolean;
  is_primary_key?: boolean;
  is_unique?: boolean;
  references?: string | null;
  comment?: string | null;
}

export interface SchemaTable {
  schema: string;
  name: string;
  kind?: string;
  comment?: string | null;
  row_estimate?: number;
  columns: SchemaColumn[];
  foreign_keys?: { columns: string[]; ref_table: string; ref_columns: string[] }[];
}

export interface SchemaCatalog {
  database: string;
  fingerprint: string;
  tables: SchemaTable[];
}

export interface RolePolicyInfo {
  name: string;
  description: string | null;
  max_rows: number | null;
  requires: string[];
  denied_columns: string[];
  denied_tables: string[];
  row_filter_tables: string[];
}

// ---------------------------------------------------------------------------
// `POST /execute` — user-supplied SQL, no model call
// ---------------------------------------------------------------------------
export interface ExecuteResult {
  ok: boolean;
  sql: string | null;
  stage: 'validation' | 'policy' | 'execution' | null;
  error: string | null;
  validation: Record<string, unknown>;
  policy: Partial<PolicyInfo> & { applied_filters?: PolicyFilter[] };
  columns: string[];
  rows: CellValue[][];
  row_count: number;
  duration_ms: number;
  truncated: boolean;
  plan: string[];
  max_rows: number;
  role: string;
}

// ---------------------------------------------------------------------------
// Workbench, history and board
// ---------------------------------------------------------------------------
export interface WorkbenchResult {
  id: string;
  title: string;
  question: string;
  artifact: ArtifactData;
  meta?: SqlMeta;
  /** Set once the user runs an edited query in the SQL tab. */
  edited?: boolean;
  generatedSql?: string | null;
}

export interface HistoryEntry {
  id: string;
  question: string;
  sql: string;
  rowCount: number | null;
  durationMs: number | null;
  outcome?: Outcome;
  role: string;
  at: number;
}

export interface BoardTile {
  id: string;
  title: string;
  artifact: ArtifactData;
  spec: ChartSpec;
  meta?: SqlMeta;
  question: string;
}
