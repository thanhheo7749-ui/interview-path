import { useEffect, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { KB_CHANGED_EVENT, getReviewQueue, listConflicts } from './kb.js';

// Open review items and open conflicts, for the sidebar badges. HR only. Refreshes on navigation and on kb-changed.
export function useKbCounts(companyId, enabled) {
  const [counts, setCounts] = useState({ review: 0, conflicts: 0 });
  const [tick, setTick] = useState(0);
  const { pathname } = useLocation();

  useEffect(() => {
    const bump = () => setTick((n) => n + 1);
    window.addEventListener(KB_CHANGED_EVENT, bump);
    return () => window.removeEventListener(KB_CHANGED_EVENT, bump);
  }, []);

  useEffect(() => {
    if (!enabled || companyId == null) return undefined;
    let cancelled = false;
    Promise.all([getReviewQueue(companyId), listConflicts(companyId)])
      .then(([queue, conflicts]) => {
        if (!cancelled) setCounts({ review: queue.nodes.length, conflicts: conflicts.length });
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [companyId, enabled, tick, pathname]);

  return enabled ? counts : { review: 0, conflicts: 0 };
}
