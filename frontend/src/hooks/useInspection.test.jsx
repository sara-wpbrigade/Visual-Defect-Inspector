import { act, renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { STATUS } from '../constants';
import { createInspection } from '../services/api';
import { useInspection } from './useInspection';

vi.mock('../services/api', () => ({ createInspection: vi.fn() }));

const photo = new File(['photo'], 'bottle.png', { type: 'image/png' });

const RESULT = {
  inspectionId: 'abc123',
  score: 0.9,
  assessment: {
    verdict: 'defect',
    confidence: 0.9,
    needsReview: false,
    severity: 'high',
    areaRatio: 0.17,
    action: 'reject',
  },
};

beforeEach(() => {
  createInspection.mockReset();
});

describe('useInspection', () => {
  it('starts idle with no result and no error', () => {
    const { result } = renderHook(() => useInspection());

    expect(result.current.status).toBe(STATUS.IDLE);
    expect(result.current.result).toBeNull();
    expect(result.current.error).toBeNull();
  });

  it('moves to loading, then success with the inspection', async () => {
    createInspection.mockResolvedValue(RESULT);
    const { result } = renderHook(() => useInspection());

    await act(async () => {
      await result.current.inspect(photo);
    });

    expect(createInspection).toHaveBeenCalledWith(photo);
    expect(result.current.status).toBe(STATUS.SUCCESS);
    expect(result.current.result).toEqual(RESULT);
    expect(result.current.error).toBeNull();
  });

  it('reports loading while the request is in flight', async () => {
    let resolveRequest;
    createInspection.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveRequest = resolve;
        }),
    );
    const { result } = renderHook(() => useInspection());
    let request;

    act(() => {
      request = result.current.inspect(photo);
    });
    expect(result.current.status).toBe(STATUS.LOADING);

    await act(async () => {
      resolveRequest(RESULT);
      await request;
    });
    expect(result.current.status).toBe(STATUS.SUCCESS);
  });

  it('moves to error and returns null when the request fails', async () => {
    const failure = new Error('Network down');
    createInspection.mockRejectedValue(failure);
    const { result } = renderHook(() => useInspection());
    let returned;

    await act(async () => {
      returned = await result.current.inspect(photo);
    });

    expect(returned).toBeNull();
    expect(result.current.status).toBe(STATUS.ERROR);
    expect(result.current.error).toBe(failure);
    expect(result.current.result).toBeNull();
  });

  it('resets back to the idle state', async () => {
    createInspection.mockResolvedValue(RESULT);
    const { result } = renderHook(() => useInspection());
    await act(async () => {
      await result.current.inspect(photo);
    });

    act(() => {
      result.current.reset();
    });

    expect(result.current.status).toBe(STATUS.IDLE);
    expect(result.current.result).toBeNull();
  });
});
