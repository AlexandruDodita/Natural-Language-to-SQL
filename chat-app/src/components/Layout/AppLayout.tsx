import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type {
  ArtifactData,
  BoardTile,
  ChartSpec,
  ExecuteResult,
  HistoryEntry,
  Message,
  QueryEngine,
  SchemaTable,
  UserContext,
  WorkbenchResult,
} from '../../types';
import { useChat } from '../../hooks/useChat';
import { useSchema } from '../../hooks/useSchema';
import { useTheme } from '../../hooks/useTheme';
import { defaultSpec } from '../../lib/shape';
import { ragApi } from '../../services/api';
import { TopBar, type View } from './TopBar';
import { Rail } from '../Rail/Rail';
import { Stream } from '../Chat/Stream';
import { Composer } from '../Composer/Composer';
import { BoardView } from '../Board/BoardView';
import { WorkbenchPanel, type WorkbenchTab } from '../Workbench/WorkbenchPanel';
import { Toast } from '../ui/Toast';
import { useToast } from '../../hooks/useToast';

const EMPTY_ARTIFACT: ArtifactData = { columns: [], rows: [], chart: null };

export function AppLayout() {
  const { theme, toggle: toggleTheme } = useTheme();
  const { catalog, roles, serviceMaxRows, error: schemaError, loading: schemaLoading } = useSchema();
  const { message: toastMessage, toast } = useToast();

  const {
    conversations,
    currentConversation,
    currentConversationId,
    isStreaming,
    history,
    sendMessage,
    retryLastMessage,
    startNewConversation,
    selectConversation,
    deleteConversation,
    clearHistory,
  } = useChat();

  const [railOpen, setRailOpen] = useState(() => window.innerWidth > 820);
  const [panelOpen, setPanelOpen] = useState(false);
  const [view, setView] = useState<View>('chat');

  const [engine, setEngine] = useState<QueryEngine>('rag');
  const [role, setRole] = useState('manager');
  const [locationId, setLocationId] = useState<number | null>(null);

  const [draft, setDraft] = useState('');
  const [result, setResult] = useState<WorkbenchResult | null>(null);
  const [specs, setSpecs] = useState<Record<string, ChartSpec>>({});
  const [tab, setTab] = useState<WorkbenchTab>('chart');
  const [tiles, setTiles] = useState<BoardTile[]>([]);
  const [running, setRunning] = useState(false);

  const user: UserContext = useMemo(
    () => ({ role, location_id: locationId, user_id: null }),
    [role, locationId],
  );

  const activeRole = roles.find(r => r.name === role);
  // `Pipeline._validator` takes the smaller of the two, so reporting the role
  // cap alone would overstate what a query is allowed to return.
  const caps = [serviceMaxRows, activeRole?.max_rows].filter(
    (n): n is number => typeof n === 'number',
  );
  const maxRows = caps.length ? Math.min(...caps) : null;

  // The mockup keys its layout off body classes; keeping that means the ported
  // CSS — including every breakpoint — works unchanged.
  useEffect(() => {
    document.body.classList.toggle('rail-closed', !railOpen);
    document.body.classList.toggle('panel-closed', !panelOpen);
    document.body.dataset.view = view;
  }, [railOpen, panelOpen, view]);

  // Below 1180 the workbench is an overlay and below 820 the rail is one too;
  // crossing either breakpoint closes the overlay so the conversation keeps the
  // full width. Reopening one at that size is still the user's call.
  const lastWidth = useRef(window.innerWidth);
  useEffect(() => {
    const onResize = () => {
      const w = window.innerWidth;
      const was = lastWidth.current;
      if (w <= 1180 && was > 1180) setPanelOpen(false);
      if (w <= 820 && was > 820) setRailOpen(false);
      lastWidth.current = w;
    };
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);

  const messages = useMemo(() => currentConversation?.messages ?? [], [currentConversation]);

  const lastMeta = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].sqlMeta) return messages[i].sqlMeta;
    }
    return undefined;
  }, [messages]);

  const retrieved = lastMeta?.retrieval?.tables ?? [];

  const specFor = useCallback(
    (r: WorkbenchResult) => specs[r.id] ?? defaultSpec(r.artifact, r.title),
    [specs],
  );

  // -- opening results ------------------------------------------------------
  const openResult = useCallback(
    (message: Message, nextTab: WorkbenchTab = 'chart') => {
      const artifact = message.artifact ?? EMPTY_ARTIFACT;
      const meta = message.sqlMeta;
      const turn = messages.findIndex(m => m.id === message.id);
      let asked = '';
      for (let i = (turn === -1 ? messages.length : turn) - 1; i >= 0; i--) {
        if (messages[i].role === 'user') {
          asked = messages[i].content;
          break;
        }
      }
      const next: WorkbenchResult = {
        id: message.id,
        title: artifact.chart?.title || `Result ${(meta?.request_id ?? message.id).slice(0, 6)}`,
        question: asked,
        artifact,
        meta,
        generatedSql: meta?.sql ?? null,
      };
      setResult(next);
      setSpecs(s => (s[next.id] ? s : { ...s, [next.id]: defaultSpec(artifact, next.title) }));
      setTab(artifact.columns.length ? nextTab : nextTab === 'chart' ? 'sql' : nextTab);
      setPanelOpen(true);
      setView('chat');
    },
    [messages],
  );

  const openArtifact = useCallback(
    (next: WorkbenchResult, nextTab: WorkbenchTab = 'chart') => {
      setResult(next);
      setSpecs(s => ({ ...s, [next.id]: s[next.id] ?? defaultSpec(next.artifact, next.title) }));
      setTab(nextTab);
      setPanelOpen(true);
    },
    [],
  );

  // -- user-supplied SQL ----------------------------------------------------
  const runSql = useCallback(
    async (sql: string): Promise<ExecuteResult | null> => {
      setRunning(true);
      try {
        const out = await ragApi.execute(sql, user);
        if (out.ok) {
          setResult(prev =>
            prev
              ? {
                  ...prev,
                  edited: true,
                  artifact: {
                    columns: out.columns,
                    rows: out.rows,
                    chart: prev.artifact.chart,
                    truncated: out.truncated,
                    row_count: out.row_count,
                  },
                  meta: {
                    ...(prev.meta ?? { sql: null, row_count: null, duration_ms: null, blocked: null }),
                    sql: out.sql,
                    row_count: out.row_count,
                    duration_ms: out.duration_ms,
                    truncated: out.truncated,
                    role: out.role,
                    max_rows: out.max_rows,
                  },
                }
              : prev,
          );
          toast(`${out.row_count} rows in ${out.duration_ms.toFixed(0)} ms`);
          setTab('table');
        }
        return out;
      } catch (e) {
        toast(e instanceof Error ? e.message : 'Execution failed');
        return null;
      } finally {
        setRunning(false);
      }
    },
    [user, toast],
  );

  const explainSql = useCallback(
    async (sql: string): Promise<ExecuteResult | null> => {
      setRunning(true);
      try {
        return await ragApi.explain(sql, user);
      } catch (e) {
        toast(e instanceof Error ? e.message : 'EXPLAIN failed');
        return null;
      } finally {
        setRunning(false);
      }
    },
    [user, toast],
  );

  const rerunHistory = useCallback(
    async (entry: HistoryEntry) => {
      setRunning(true);
      try {
        const out = await ragApi.execute(entry.sql, user);
        if (!out.ok) {
          toast(out.error ?? 'Re-run failed');
          return;
        }
        openArtifact(
          {
            id: `history-${entry.id}-${Date.now()}`,
            title: entry.question,
            question: entry.question,
            generatedSql: entry.sql,
            artifact: {
              columns: out.columns,
              rows: out.rows,
              chart: null,
              truncated: out.truncated,
              row_count: out.row_count,
            },
            meta: {
              sql: out.sql,
              row_count: out.row_count,
              duration_ms: out.duration_ms,
              blocked: null,
              outcome: 'answered',
              role: out.role,
              max_rows: out.max_rows,
              truncated: out.truncated,
            },
          },
          'table',
        );
        toast('Replayed the stored SQL — no model call');
      } catch (e) {
        toast(e instanceof Error ? e.message : 'Re-run failed');
      } finally {
        setRunning(false);
      }
    },
    [user, openArtifact, toast],
  );

  // -- board ----------------------------------------------------------------
  const pinned = !!result && tiles.some(t => t.id === result.id);

  const togglePin = useCallback(() => {
    if (!result) return;
    setTiles(prev => {
      if (prev.some(t => t.id === result.id)) return prev.filter(t => t.id !== result.id);
      return [
        ...prev,
        {
          id: result.id,
          title: result.title,
          artifact: result.artifact,
          spec: specFor(result),
          meta: result.meta,
          question: result.question,
        },
      ];
    });
    toast(pinned ? 'Unpinned' : 'Pinned to the board');
  }, [result, specFor, pinned, toast]);

  const refreshTile = useCallback(
    async (tile: BoardTile) => {
      const sql = tile.meta?.sql;
      if (!sql) {
        toast('This tile has no stored SQL to re-run');
        return;
      }
      setRunning(true);
      try {
        const out = await ragApi.execute(sql, user);
        if (!out.ok) {
          toast(out.error ?? 'Refresh failed');
          return;
        }
        setTiles(prev =>
          prev.map(t =>
            t.id === tile.id
              ? {
                  ...t,
                  artifact: {
                    ...t.artifact,
                    columns: out.columns,
                    rows: out.rows,
                    truncated: out.truncated,
                  },
                  meta: { ...t.meta!, row_count: out.row_count, duration_ms: out.duration_ms },
                }
              : t,
          ),
        );
        toast(`${tile.title}: ${out.row_count} rows`);
      } finally {
        setRunning(false);
      }
    },
    [user, toast],
  );

  // -- sending --------------------------------------------------------------
  const ask = useCallback(
    (text: string) => {
      const content = text.trim();
      if (!content) return;
      setDraft('');
      setView('chat');
      void sendMessage(content, engine, user);
    },
    [sendMessage, engine, user],
  );

  const retryAs = useCallback(
    (nextRole: string) => {
      setRole(nextRole);
      void retryLastMessage(engine, { ...user, role: nextRole });
    },
    [retryLastMessage, engine, user],
  );

  const starters = useMemo(() => {
    if (!catalog?.tables.length) return [];
    const biggest = [...catalog.tables]
      .sort((a, b) => (b.row_estimate ?? 0) - (a.row_estimate ?? 0))
      .slice(0, 3);
    const out: string[] = [];
    for (const t of biggest) {
      // A foreign key is numeric but never a measure, so "top 10 by client_id"
      // is not a question anyone wants to ask.
      const numeric = t.columns.find(
        c =>
          /int|numeric|decimal|real|double|money/i.test(c.data_type) &&
          !c.is_primary_key &&
          !c.references &&
          !/_id$|^id$/i.test(c.name),
      );
      out.push(`How many ${t.name} are there?`);
      if (numeric) out.push(`Top 10 ${t.name} by ${numeric.name}`);
    }
    return out.slice(0, 4);
  }, [catalog]);

  const pickTable = useCallback((t: SchemaTable) => {
    setDraft(d => `${d}${d && !d.endsWith(' ') ? ' ' : ''}${t.name} `);
  }, []);

  return (
    <div className="app">
      <TopBar
        catalog={catalog}
        roles={roles}
        role={role}
        onRoleChange={setRole}
        locationId={locationId}
        onLocationChange={setLocationId}
        engine={engine}
        onEngineChange={setEngine}
        view={view}
        onViewChange={setView}
        boardCount={tiles.length}
        theme={theme}
        onToggleTheme={toggleTheme}
        onToggleRail={() => setRailOpen(o => !o)}
        onTogglePanel={() => setPanelOpen(o => !o)}
        panelOpen={panelOpen}
        disabled={isStreaming}
      />

      <div className="rail-scrim" onClick={() => setRailOpen(false)} />
      <Rail
        conversations={conversations}
        currentConversationId={currentConversationId}
        onSelectConversation={id => {
          void selectConversation(id);
          if (window.innerWidth <= 820) setRailOpen(false);
        }}
        onDeleteConversation={id => void deleteConversation(id)}
        onNewChat={() => {
          startNewConversation();
          setResult(null);
          setPanelOpen(false);
        }}
        catalog={catalog}
        schemaLoading={schemaLoading}
        schemaError={schemaError}
        retrieved={retrieved}
        onPickTable={pickTable}
        history={history}
        onRerun={entry => void rerunHistory(entry)}
        onClearHistory={clearHistory}
        busy={running || isStreaming}
      />

      <main className="main">
        <Stream
          messages={messages}
          isStreaming={isStreaming}
          database={catalog?.database ?? null}
          onOpenResult={openResult}
          onAsk={ask}
          onRetry={() => void retryLastMessage(engine, user)}
          onRetryAs={retryAs}
          onPrefill={text => setDraft(text)}
        />

        <BoardView
          tiles={tiles}
          busy={running}
          onOpen={tile =>
            openArtifact(
              {
                id: tile.id,
                title: tile.title,
                question: tile.question,
                artifact: tile.artifact,
                meta: tile.meta,
                generatedSql: tile.meta?.sql ?? null,
              },
              'chart',
            )
          }
          onUnpin={id => setTiles(prev => prev.filter(t => t.id !== id))}
          onRefresh={tile => void refreshTile(tile)}
          onToast={toast}
        />

        <Composer
          value={draft}
          onChange={setDraft}
          onSend={() => ask(draft)}
          disabled={isStreaming}
          engine={engine}
          role={role}
          maxRows={maxRows}
          starters={messages.length === 0 ? starters : []}
          onStarter={ask}
        />
      </main>

      <div className="panel-scrim" onClick={() => setPanelOpen(false)} />
      <WorkbenchPanel
        result={result}
        spec={result ? specFor(result) : defaultSpec(EMPTY_ARTIFACT)}
        onSpecChange={patch =>
          result &&
          setSpecs(s => ({ ...s, [result.id]: { ...specFor(result), ...patch } }))
        }
        tab={tab}
        onTabChange={setTab}
        onClose={() => setPanelOpen(false)}
        onPin={togglePin}
        pinned={pinned}
        onRun={runSql}
        onExplain={explainSql}
        role={role}
        busy={running || isStreaming}
        tableCount={catalog?.tables.length ?? null}
        onToast={toast}
      />

      <Toast message={toastMessage} />
    </div>
  );
}
