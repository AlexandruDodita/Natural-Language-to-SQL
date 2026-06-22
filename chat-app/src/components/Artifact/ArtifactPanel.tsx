import { useState } from 'react';
import type { ArtifactData } from '../../types';
import { ArtifactChart } from './ArtifactChart';
import { ArtifactTable } from './ArtifactTable';

const RAG_URL = import.meta.env.VITE_RAG_URL || 'http://localhost:8100';

interface ArtifactPanelProps {
  artifact: ArtifactData;
  onClose: () => void;
}

type Tab = 'chart' | 'table';

export function ArtifactPanel({ artifact, onClose }: ArtifactPanelProps) {
  const hasChart = artifact.chart !== null;
  const [activeTab, setActiveTab] = useState<Tab>(hasChart ? 'chart' : 'table');
  const [downloading, setDownloading] = useState(false);

  const handleDownload = async () => {
    setDownloading(true);
    try {
      const resp = await fetch(`${RAG_URL}/report`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          columns: artifact.columns,
          rows: artifact.rows,
          chart: artifact.chart,
          title: artifact.chart?.title || 'Report',
        }),
      });
      if (!resp.ok) throw new Error('Report generation failed');
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${artifact.chart?.title || 'report'}.xlsx`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      console.error('Download failed:', e);
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div className="h-full flex flex-col bg-[#1e1e1e] border-l border-white/10">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-white/10 shrink-0">
        <div className="flex items-center gap-3">
          <h2 className="text-sm font-medium text-white/90 truncate">
            {artifact.chart?.title || 'Query Results'}
          </h2>
          <span className="text-[11px] text-white/40">
            {artifact.rows.length} row{artifact.rows.length !== 1 ? 's' : ''}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleDownload}
            disabled={downloading}
            className="flex items-center gap-1.5 px-3 py-1.5 text-[12px] bg-blue-600/80 hover:bg-blue-600 text-white rounded-md transition-colors disabled:opacity-50"
          >
            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v12m0 0l-4-4m4 4l4-4M4 18h16" />
            </svg>
            {downloading ? 'Generating...' : 'Excel'}
          </button>
          <button
            onClick={onClose}
            className="p-1.5 text-white/40 hover:text-white/80 transition-colors rounded"
            aria-label="Close panel"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>

      {/* Tabs */}
      {hasChart && (
        <div className="flex border-b border-white/10 shrink-0">
          <button
            onClick={() => setActiveTab('chart')}
            className={`px-4 py-2 text-[13px] transition-colors ${activeTab === 'chart' ? 'text-white border-b-2 border-blue-500' : 'text-white/50 hover:text-white/70'}`}
          >
            Chart
          </button>
          <button
            onClick={() => setActiveTab('table')}
            className={`px-4 py-2 text-[13px] transition-colors ${activeTab === 'table' ? 'text-white border-b-2 border-blue-500' : 'text-white/50 hover:text-white/70'}`}
          >
            Table
          </button>
        </div>
      )}

      {/* Content */}
      <div className="flex-1 overflow-auto p-4">
        {activeTab === 'chart' && hasChart ? (
          <ArtifactChart artifact={artifact} />
        ) : (
          <ArtifactTable columns={artifact.columns} rows={artifact.rows} />
        )}
      </div>
    </div>
  );
}
