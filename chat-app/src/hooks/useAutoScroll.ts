import { useEffect, useRef } from 'react';

/**
 * Keeps the stream pinned to the bottom while an answer is being written, and
 * gets out of the way as soon as the reader scrolls up.
 */
export function useAutoScroll<T extends HTMLElement>(dependency: unknown): React.RefObject<T | null> {
  const ref = useRef<T>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    if (distanceFromBottom < 240) el.scrollTop = el.scrollHeight;
  }, [dependency]);

  return ref;
}
