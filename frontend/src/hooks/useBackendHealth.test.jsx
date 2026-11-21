import { act, renderHook, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { useBackendHealth } from './useBackendHealth';

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe('useBackendHealth', () => {
  it('reports ok when the health endpoint answers', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true });
    vi.stubGlobal('fetch', fetchMock);

    const { result } = renderHook(() => useBackendHealth());

    await waitFor(() => expect(result.current).toBe('ok'));
    expect(fetchMock).toHaveBeenCalledWith('/health', expect.objectContaining({ method: 'GET' }));
  });

  it('reports down for a failed response or a rejected request', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false }));

    const { result } = renderHook(() => useBackendHealth());
    await waitFor(() => expect(result.current).toBe('down'));

    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('offline')));
    const second = renderHook(() => useBackendHealth());
    await waitFor(() => expect(second.result.current).toBe('down'));
  });

  it('checks again on the polling interval', async () => {
    vi.useFakeTimers();
    const fetchMock = vi.fn().mockResolvedValue({ ok: true });
    vi.stubGlobal('fetch', fetchMock);

    renderHook(() => useBackendHealth());
    await act(async () => {
      await vi.advanceTimersByTimeAsync(0);
    });
    expect(fetchMock).toHaveBeenCalledTimes(1);

    await act(async () => {
      await vi.advanceTimersByTimeAsync(30_000);
    });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
