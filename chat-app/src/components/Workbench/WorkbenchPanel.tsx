import { useState } from 'react';
import type { ChartSpec, ExecuteResult, WorkbenchResult } from '../../types';
import { fmtMs } from '../../lib/format';
import { download, toCsv } from '../../lib/sql';
import { ragApi } from '../../services/api';
import { ChartPane } from './ChartPane';
import { TablePane } from './TablePane';
import { SqlPane } from './SqlPane';
import { ProvenancePane } from './ProvenancePane';

export type WorkbenchTab = 'chart' | 'table' | 'sql' | 'prov';

interface WorkbenchPanelProps {
  result: WorkbenchResult | null;
  spec: ChartSpec;
  onSpecChange: (patch: Partial<ChartSpec>) => void;
  tab: WorkbenchTab;
  onTabChange: (tab: WorkbenchTab) => void;
  onClose: () => void;
  onPin: () => void;
  pinned: boolean;
  onRun: (sql: string) => Promise<ExecuteResult | null>;
  onExplain: (sql: string) => Promise<ExecuteResult | null>;
  role: string;
  busy: boolean;
  tableCount: number | null;
  onToast: (message: string) => void;
}

export function WorkbenchPanel({
  result,
  spec,
  onSpecChange,
  tab,
  onTabChange,
  onClose,
  onPin,
  pinned,
  onRun,
  onExplain,
  role,
  busy,
  tableCount,
  onToast,
}: WorkbenchPanelProps) {
  const [exporting, setExporting] = useState(false);

  if (!result) {
    return (
      <aside className="panel" aria-label="Result workbench">
        <div className="panel-head">
          <div className="t">
            <b>Workbench</b>
            <div className="sub">nothing open</div>
          </div>
          <button className="btn btn-ghost btn-sm" onClick={onClose} aria-label="Close">
            ✕
          </button>
        </div>
        <div className="panel-body">
          <div className="pane" data-active="true">
            <p className="chart-note">
              Open a result from a turn in the conversation, or re-run one from the query history.
            </p>
          </div>
        </div>
      </aside>
    );
  }

  const { artifact, meta } = result;
  const rows = artifact.rows.length;

  const exportExcel = async () => {
    setExporting(true);
    try {
      const blob = await ragApi.report(artifact, result.title);
      download(`${result.title || 'report'}.xlsx`, blob);
      onToast('Exported as XLSX');
    } catch (e) {
      onToast(e instanceof Error ? e.message : 'Export failed');
    } finally {
      setExporting(false);
    }
  };

  return (
    <aside className="panel" aria-label="Result workbench">
      <div className="panel-head">
        <div className="t">
          <b>{result.title}</b>
          <div className="sub">
            <span>
              {rows} row{rows === 1 ? '' : 's'}
            </span>
            {meta?.duration_ms !== null && meta?.duration_ms !== undefined && (
              <>
                <span>·</span>
                <span>{fmtMs(meta.duration_ms)}</span>
              </>
            )}
            {result.edited && (
              <>
                <span>·</span>
                <span className="chip chip-warn">
                  <span className="dot" />
                  edited
                </span>
              </>
            )}
          </div>
        </div>
        <button className="btn btn-sm" onClick={exportExcel} disabled={exporting}>
          {exporting ? 'Exporting…' : 'Excel'}
        </button>
        <button
          className="btn btn-sm"
          onClick={() => {
            download(`${result.title || 'result'}.csv`, toCsv(artifact.columns, artifact.rows), 'text/csv');
            onToast('Exported as CSV');
          }}
        >
          CSV
        </button>
        <button className="btn btn-ghost btn-sm" onClick={onPin} title="Pin to board">
          {pinned ? 'Pinned' : 'Pin'}
        </button>
        <button className="btn btn-ghost btn-sm" onClick={onClose} aria-label="Close">
          ✕
        </button>
      </div>

      <nav className="tabs" role="tablist">
        {(
          [
            ['chart', 'Chart'],
            ['table', 'Table'],
            ['sql', 'SQL'],
            ['prov', 'Provenance'],
          ] as [WorkbenchTab, string][]
        ).map(([key, label]) => (
          <button
            key={key}
            role="tab"
            aria-selected={tab === key}
            onClick={() => onTabChange(key)}
          >
            {label}
            {key === 'table' && <span className="badge">{rows}</span>}
          </button>
        ))}
      </nav>

      <div className="panel-body">
        <section className="pane" data-active={tab === 'chart'}>
          {tab === 'chart' && (
            <ChartPane artifact={artifact} spec={spec} onSpecChange={onSpecChange} />
          )}
        </section>

        <section className="pane" data-active={tab === 'table'}>
          {tab === 'table' && (
            <TablePane artifact={artifact} maxRows={meta?.policy?.max_rows ?? meta?.max_rows} />
          )}
        </section>

        <section className="pane" data-active={tab === 'sql'}>
          {tab === 'sql' &&
            (meta?.sql || result.generatedSql ? (
              <SqlPane
                key={result.id}
                sql={meta?.sql ?? result.generatedSql ?? ''}
                generatedSql={result.generatedSql ?? meta?.sql ?? null}
                role={role}
                maxRows={meta?.policy?.max_rows ?? meta?.max_rows}
                onRun={onRun}
                onExplain={onExplain}
                busy={busy}
              />
            ) : (
              <p className="chart-note">No SQL was generated for this turn.</p>
            ))}
        </section>

        <section className="pane" data-active={tab === 'prov'}>
          {tab === 'prov' && <ProvenancePane meta={meta} tableCount={tableCount} />}
        </section>
      </div>
    </aside>
  );
}
