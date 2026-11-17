import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  GENERIC_ERROR_MESSAGE,
  MAX_IMAGE_MEGABYTES,
  NETWORK_ERROR_MESSAGE,
  UNEXPECTED_RESPONSE_MESSAGE,
} from '../constants';
import { ApiError, createInspection } from './api';

const photo = new File(['photo-bytes'], 'bottle.png', { type: 'image/png' });

const API_PAYLOAD = {
  inspection_id: 'abc123',
  score: 0.9369,
  assessment: {
    verdict: 'defect',
    confidence: 0.9369,
    needs_review: false,
    severity: 'high',
    area_ratio: 0.175,
    action: 'reject',
  },
};

const VIEW_MODEL = {
  inspectionId: 'abc123',
  score: 0.9369,
  assessment: {
    verdict: 'defect',
    confidence: 0.9369,
    needsReview: false,
    severity: 'high',
    areaRatio: 0.175,
    action: 'reject',
  },
};

function jsonResponse(status, body) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json:
      body === undefined
        ? async () => {
            throw new SyntaxError('not JSON');
          }
        : async () => body,
  };
}

function stubFetch(response) {
  const fetchMock = vi.fn().mockResolvedValue(response);
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('createInspection', () => {
  it('posts the photo to /inspections and normalizes the response', async () => {
    const fetchMock = stubFetch(jsonResponse(201, API_PAYLOAD));

    await expect(createInspection(photo)).resolves.toEqual(VIEW_MODEL);

    const [url, options] = fetchMock.mock.calls[0];
    expect(url).toBe('/inspections');
    expect(options.method).toBe('POST');
    expect(options.body).toBeInstanceOf(FormData);
    expect(options.body.get('image')).toBe(photo);
    expect(options.headers).toBeUndefined();
  });

  it('maps a bad image to an operator-friendly message', async () => {
    stubFetch(jsonResponse(400, { detail: 'The upload is not a valid image.' }));

    await expect(createInspection(photo)).rejects.toMatchObject({
      name: 'ApiError',
      status: 400,
      message: 'The server could not read this image. Use a JPEG or PNG photo.',
    });
  });

  it('maps an oversized photo with the same limit the UI shows', async () => {
    stubFetch(jsonResponse(413, { detail: 'too large' }));

    await expect(createInspection(photo)).rejects.toMatchObject({
      status: 413,
      message: expect.stringContaining(`${MAX_IMAGE_MEGABYTES} MB`),
    });
  });

  it('maps a missing photo field and an unavailable model', async () => {
    stubFetch(jsonResponse(422, { detail: [{ msg: 'Field required' }] }));
    await expect(createInspection(photo)).rejects.toMatchObject({ status: 422 });

    stubFetch(jsonResponse(503, { detail: 'model failed' }));
    await expect(createInspection(photo)).rejects.toMatchObject({
      status: 503,
      message: expect.stringContaining('unavailable'),
    });
  });

  it('reports a network failure when fetch rejects', async () => {
    const fetchMock = vi.fn().mockRejectedValue(new TypeError('Failed to fetch'));
    vi.stubGlobal('fetch', fetchMock);

    await expect(createInspection(photo)).rejects.toMatchObject({
      name: 'ApiError',
      status: 0,
      message: NETWORK_ERROR_MESSAGE,
    });
  });

  it('falls back to the server detail for an unmapped status', async () => {
    stubFetch(jsonResponse(500, { detail: 'Storage is read-only.' }));

    await expect(createInspection(photo)).rejects.toMatchObject({
      status: 500,
      message: 'Storage is read-only.',
    });
  });

  it('joins FastAPI validation details for an unmapped status', async () => {
    stubFetch(jsonResponse(500, { detail: [{ msg: 'Bad header' }, { msg: 7 }, null] }));

    await expect(createInspection(photo)).rejects.toMatchObject({
      status: 500,
      message: 'Bad header',
    });
  });

  it('uses the generic message when an error body is not JSON', async () => {
    stubFetch(jsonResponse(502, undefined));

    await expect(createInspection(photo)).rejects.toMatchObject({
      status: 502,
      message: GENERIC_ERROR_MESSAGE,
    });
  });

  it('rejects a success response that does not match the contract', async () => {
    stubFetch(jsonResponse(201, { score: 0.5 }));

    await expect(createInspection(photo)).rejects.toMatchObject({
      name: 'ApiError',
      message: UNEXPECTED_RESPONSE_MESSAGE,
    });
  });

  it('builds ApiError with a safe default status', () => {
    const error = new ApiError('boom');

    expect(error).toBeInstanceOf(Error);
    expect(error.status).toBe(0);
    expect(error.detail).toBeNull();
  });
});
