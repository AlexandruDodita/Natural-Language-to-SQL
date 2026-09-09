import { useEffect, useState } from 'react';
import { ragApi } from '../services/api';
import type { RolePolicyInfo, SchemaCatalog } from '../types';

/**
 * `GET /schema` and `GET /roles` were both implemented and never called. The
 * rail renders the first; the top bar's role selector is driven by the second.
 */
export function useSchema() {
  const [catalog, setCatalog] = useState<SchemaCatalog | null>(null);
  const [roles, setRoles] = useState<RolePolicyInfo[]>([]);
  const [serviceMaxRows, setServiceMaxRows] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const cat = await ragApi.schema();
        if (alive) setCatalog(cat);
      } catch (e) {
        if (alive) setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (alive) setLoading(false);
      }
      try {
        const r = await ragApi.roles();
        if (alive) setRoles(r.roles);
      } catch {
        // the role list falls back to the four names in policy.yaml
      }
      try {
        // The row cap a query actually gets is min(service, role) — see
        // Pipeline._validator — so the composer needs both numbers.
        const c = await ragApi.config();
        const cap = c.knobs?.max_rows;
        if (alive && typeof cap === 'number') setServiceMaxRows(cap);
      } catch {
        // not fatal: the composer then reports the role cap alone
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  return { catalog, roles, serviceMaxRows, error, loading };
}
