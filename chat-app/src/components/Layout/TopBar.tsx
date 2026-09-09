import type { QueryEngine, RolePolicyInfo, SchemaCatalog } from '../../types';

export type View = 'chat' | 'board';

interface TopBarProps {
  catalog: SchemaCatalog | null;
  roles: RolePolicyInfo[];
  role: string;
  onRoleChange: (role: string) => void;
  locationId: number | null;
  onLocationChange: (id: number | null) => void;
  engine: QueryEngine;
  onEngineChange: (engine: QueryEngine) => void;
  view: View;
  onViewChange: (view: View) => void;
  boardCount: number;
  theme: string;
  onToggleTheme: () => void;
  onToggleRail: () => void;
  onTogglePanel: () => void;
  panelOpen: boolean;
  disabled: boolean;
}

const FALLBACK_ROLES = ['manager', 'agent', 'analyst', 'auditor'];

export function TopBar({
  catalog,
  roles,
  role,
  onRoleChange,
  locationId,
  onLocationChange,
  engine,
  onEngineChange,
  view,
  onViewChange,
  boardCount,
  theme,
  onToggleTheme,
  onToggleRail,
  onTogglePanel,
  panelOpen,
  disabled,
}: TopBarProps) {
  const names = roles.length ? roles.map(r => r.name) : FALLBACK_ROLES;
  const active = roles.find(r => r.name === role);
  const needsLocation = (active?.requires ?? []).includes('location_id');

  return (
    <header className="topbar">
      <button className="btn btn-ghost btn-sm" onClick={onToggleRail} aria-label="Toggle sidebar" title="Sidebar">
        ☰
      </button>
      <div className="brand">
        <span className="mark">Q</span>
        <span className="hide-xs">NL2SQL Workbench</span>
      </div>
      <div className="sep hide-sm" />

      {/* The target database is configured server side (DATABASE_URL); the top
          bar reports which one is connected rather than pretending to switch. */}
      <div className="ctlgrp hide-sm" title="Introspected from the connected database">
        <span>DB</span>
        <div className="chip">
          <span className="dot" />
          {catalog ? `${catalog.database} · ${catalog.tables.length} tables` : 'connecting…'}
        </div>
      </div>

      <div className="ctlgrp hide-sm">
        <span>Role</span>
        <select
          className="ctl"
          value={role}
          disabled={disabled}
          onChange={e => onRoleChange(e.target.value)}
          title="Authorization role from policy.yaml"
        >
          {names.map(n => (
            <option key={n} value={n}>
              {n}
            </option>
          ))}
        </select>
        {needsLocation && (
          <input
            className="ctl"
            style={{ width: 74 }}
            type="number"
            min={1}
            value={locationId ?? ''}
            placeholder="branch"
            disabled={disabled}
            onChange={e => onLocationChange(e.target.value === '' ? null : Number(e.target.value))}
            title={`role '${role}' requires location_id`}
          />
        )}
      </div>

      <div className="seg hide-sm" role="group" aria-label="Query engine">
        {(['rag', 'mcp'] as QueryEngine[]).map(option => (
          <button
            key={option}
            onClick={() => onEngineChange(option)}
            aria-pressed={engine === option}
            disabled={disabled}
          >
            {option.toUpperCase()}
          </button>
        ))}
      </div>

      <div className="spacer" />

      <div className="seg" role="group" aria-label="View">
        <button onClick={() => onViewChange('chat')} aria-pressed={view === 'chat'}>
          Chat
        </button>
        <button onClick={() => onViewChange('board')} aria-pressed={view === 'board'}>
          Board {boardCount > 0 && <span className="mono">{boardCount}</span>}
        </button>
      </div>
      <button className="btn btn-sm" onClick={onToggleTheme} title="Light / dark theme">
        {theme === 'dark' ? 'Light' : 'Dark'}
      </button>
      <button className="btn btn-sm" onClick={onTogglePanel} aria-pressed={panelOpen} title="Toggle workbench">
        Workbench
      </button>
    </header>
  );
}
