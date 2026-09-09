import type { BoardTile } from '../../types';
import { fmtMs, truncate } from '../../lib/format';
import { download, toCsv } from '../../lib/sql';
import { ChartView } from '../Workbench/ChartView';

interface BoardViewProps {
  tiles: BoardTile[];
  busy: boolean;
  onOpen: (tile: BoardTile) => void;
  onUnpin: (id: string) => void;
  onRefresh: (tile: BoardTile) => void;
  onToast: (message: string) => void;
}

/**
 * Pinned results, each keeping its own SQL, its own chart spec and its own
 * refresh — which is what makes comparing two queries possible at all.
 */
export function BoardView({ tiles, busy, onOpen, onUnpin, onRefresh, onToast }: BoardViewProps) {
  const exportBoard = () => {
    if (!tiles.length) return;
    const parts = tiles.map(t => `# ${t.title}\n${toCsv(t.artifact.columns, t.artifact.rows)}`);
    download('board.csv', parts.join('\n\n'), 'text/csv');
    onToast(`Exported ${tiles.length} tile${tiles.length === 1 ? '' : 's'}`);
  };

  return (
    <section className="board">
      <div className="board-head">
        <div style={{ flex: 1 }}>
          <h2>Board</h2>
          <p>
            {tiles.length
              ? `${tiles.length} pinned quer${tiles.length === 1 ? 'y' : 'ies'}. Each tile keeps its own SQL, filters and chart spec, and refreshes independently.`
              : 'Nothing pinned yet — open a result in the workbench and press Pin.'}
          </p>
        </div>
        <button className="btn btn-sm" onClick={exportBoard} disabled={!tiles.length}>
          Export board
        </button>
      </div>

      <div className="board-grid">
        {tiles.map(tile => (
          <div className="tile" key={tile.id}>
            <div className="tile-head">
              <b>{tile.title}</b>
              <button className="btn btn-ghost btn-sm" disabled={busy} onClick={() => onRefresh(tile)}>
                Refresh
              </button>
              <button className="btn btn-ghost btn-sm" onClick={() => onOpen(tile)}>
                Open
              </button>
              <button className="btn btn-ghost btn-sm" onClick={() => onUnpin(tile.id)} aria-label="Unpin">
                ✕
              </button>
            </div>

            <ChartView artifact={tile.artifact} spec={tile.spec} height={190} compact />

            <p className="chart-note">
              {tile.artifact.rows.length} rows
              {tile.meta?.duration_ms !== null && tile.meta?.duration_ms !== undefined
                ? ` · ${fmtMs(tile.meta.duration_ms)}`
                : ''}
              {tile.meta?.retrieval?.tables?.length ? (
                <>
                  {' · '}
                  <span className="mono">{tile.meta.retrieval.tables.join(', ')}</span>
                </>
              ) : null}
              {tile.question ? ` · ${truncate(tile.question, 60)}` : ''}
            </p>
          </div>
        ))}
      </div>
    </section>
  );
}
