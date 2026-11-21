/** Polls the backend health endpoint and exposes a coarse status. */

import { useEffect, useRef, useState } from 'react';

const CHECK_INTERVAL_MS = 30_000;
const TIMEOUT_MS = 4_000;

/** @returns {'ok' | 'down' | 'checking'} */
export function useBackendHealth() {
  const [status, setStatus] = useState('checking');
  const cancelledRef = useRef(false);

  useEffect(() => {
    cancelledRef.current = false;

    async function check() {
      if (cancelledRef.current) {
        return;
      }
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), TIMEOUT_MS);
      try {
        const response = await fetch('/health', {
          method: 'GET',
          signal: controller.signal,
        });
        if (!cancelledRef.current) {
          setStatus(response.ok ? 'ok' : 'down');
        }
      } catch {
        if (!cancelledRef.current) {
          setStatus('down');
        }
      } finally {
        clearTimeout(timeout);
      }
    }

    check();
    const interval = setInterval(check, CHECK_INTERVAL_MS);

    return () => {
      cancelledRef.current = true;
      clearInterval(interval);
    };
  }, []);

  return status;
}
