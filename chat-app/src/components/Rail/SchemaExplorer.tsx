import { useMemo, useState } from 'react';
import type { SchemaCatalog, SchemaTable } from '../../types';

interface SchemaExplorerProps {
  catalog: SchemaCatalog | null;
  loading: boolean;
  error: string | null;
  /** Tables the retriever sent to the model for the active query. */
  retrieved: string[];
  onPick: (table: SchemaTable) => void;
}

const qualified = (t: SchemaTable) => (t.schema === 'public' ? t.name : `${t.schema}.${t.name}`);

export function SchemaExplorer({ catalog, loading, error, retrieved, onPick }: SchemaExplorerProps) {
  const [filter, setFilter] = useState('');

  const used = useMemo(
    () => new Set(retrieved.map(t => t.toLowerCase().split('.').pop() as string)),
    [retrieved],
  );

  const tables = useMemo(() => {
    if (!catalog) return [];
    const q = filter.trim().toLowerCase();
    if (!q) return catalog.tables;
    return catalog.tables.filter(
      t =>
        qualified(t).toLowerCase().includes(q) ||
        t.columns.some(c => c.name.toLowerCase().includes(q)),
    );
  }, [catalog, filter]);

  const columnCount = catalog?.tables.reduce((a, t) => a + t.columns.length, 0) ?? 0;

  return (
    <div className="rail-sec">
      <div className="rail-head">
        <span className="label">Schema</span>
        <span className="mono muted">
          {catalog ? `${catalog.tables.length} tables · ${columnCount} cols` : ''}
        </span>
      </div>

      <input
        className="ctl"
        value={filter}
        onChange={e => setFilter(e.target.value)}
        placeholder="Filter tables and columns…"
        style={{ width: '100%', marginBottom: 8 }}
      />

      {loading && <p className="chart-note">Introspecting…</p>}
      {error && !catalog && (
        <p className="chart-note">
          Schema unavailable — <span className="mono">GET /schema</span> returned {error}.
        </p>
      )}

      <div className="tree">
        {tables.map(t => {
          const name = qualified(t);
          const isUsed = used.has(t.name.toLowerCase());
          return (
            <details key={name} className={`tnode${isUsed ? ' used' : ''}`} open={isUsed}>
              <summary className="trow" onDoubleClick={() => onPick(t)}>
                <span className="caret">▸</span>
                <span>{name}</span>
                <span className="tcount">{t.row_estimate ? t.row_estimate.toLocaleString('en-US') : ''}</span>
              </summary>
              <div className="tcols">
                {t.columns.map(c => (
                  <div className="tcol" key={c.name}>
                    <b>{c.name}</b>
                    <span className="ty">{c.data_type}</span>
                    {c.is_primary_key && <span className="pk">PK</span>}
                    {c.references && <span className="fk" title={`→ ${c.references}`}>FK</span>}
                  </div>
                ))}
              </div>
            </details>
          );
        })}
      </div>

      <p className="chart-note" style={{ marginTop: 8 }}>
        Highlighted tables were retrieved for the active query (<span className="mono">/retrieve</span> ranking, top-k).
      </p>
    </div>
  );
}
