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
    location: { region: 'lower center', bbox: [0.348, 0.305, 0.895, 0.93] },
  },
  report: {
    report_id: 'abc123',
    generated_at: '2026-11-18T08:07:19.671664Z',
    persona: 'factory_qc_operator',
    source: 'ai',
    manual_review_notice: null,
    content: {
      summary: 'A high severity defect covers the lower center of the item.',
      findings: ['The flagged area covers 17.5% of the item.'],
      recommendations: ['Reject the item and keep it out of the batch.'],
      defect_type: 'contamination',
      voice_note_conflict: null,
    },
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
    location: { region: 'lower center', bbox: [0.348, 0.305, 0.895, 0.93] },
  },
  report: {
    reportId: 'abc123',
    generatedAt: '2026-11-18T08:07:19.671664Z',
    persona: 'factory_qc_operator',
    source: 'ai',
    manualReviewNotice: null,
    content: {
      summary: 'A high severity defect covers the lower center of the item.',
      findings: ['The flagged area covers 17.5% of the item.'],
      recommendations: ['Reject the item and keep it out of the batch.'],
      defectType: 'contamination',
      voiceNoteConflict: null,
    },
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

/** Build a payload with one field of the assessment changed. */
function withAssessment(patch) {
  return { ...API_PAYLOAD, assessment: { ...API_PAYLOAD.assessment, ...patch } };
}

/** Build a payload with one field of the report changed. */
function withReport(patch) {
  return { ...API_PAYLOAD, report: { ...API_PAYLOAD.report, ...patch } };
}

/** Build a payload with one field of the report content changed. */
function withContent(patch) {
  return withReport({ content: { ...API_PAYLOAD.report.content, ...patch } });
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

  it('keeps a pass without a location and a template report', async () => {
    const payload = withReport({
      source: 'template',
      manual_review_notice: 'This result is close to the cutoff. Review it manually.',
      content: {
        ...API_PAYLOAD.report.content,
        defect_type: null,
        voice_note_conflict: 'The voice note points to the north edge.',
      },
    });
    payload.assessment = { ...API_PAYLOAD.assessment, location: null };
    stubFetch(jsonResponse(201, payload));

    const result = await createInspection(photo);

    expect(result.assessment.location).toBeNull();
    expect(result.report.source).toBe('template');
    expect(result.report.manualReviewNotice).toContain('Review it manually');
    expect(result.report.content.defectType).toBeNull();
    expect(result.report.content.voiceNoteConflict).toContain('north edge');
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

  it('rejects a report with an unknown source or missing content', async () => {
    stubFetch(jsonResponse(201, { ...API_PAYLOAD, report: null }));
    await expect(createInspection(photo)).rejects.toMatchObject({
      message: UNEXPECTED_RESPONSE_MESSAGE,
    });

    stubFetch(jsonResponse(201, withReport({ source: 'human' })));
    await expect(createInspection(photo)).rejects.toMatchObject({
      message: UNEXPECTED_RESPONSE_MESSAGE,
    });

    stubFetch(jsonResponse(201, withReport({ content: null })));
    await expect(createInspection(photo)).rejects.toMatchObject({
      message: UNEXPECTED_RESPONSE_MESSAGE,
    });
  });

  it('rejects report lists that are empty or not text', async () => {
    stubFetch(jsonResponse(201, withContent({ findings: [] })));
    await expect(createInspection(photo)).rejects.toMatchObject({
      message: UNEXPECTED_RESPONSE_MESSAGE,
    });

    stubFetch(jsonResponse(201, withContent({ recommendations: ['ok', 7] })));
    await expect(createInspection(photo)).rejects.toMatchObject({
      message: UNEXPECTED_RESPONSE_MESSAGE,
    });
  });

  it('rejects a location that is missing or outside the photo', async () => {
    stubFetch(jsonResponse(201, withAssessment({ location: undefined })));
    await expect(createInspection(photo)).rejects.toMatchObject({
      message: UNEXPECTED_RESPONSE_MESSAGE,
    });

    stubFetch(
      jsonResponse(
        201,
        withAssessment({ location: { region: 'lower center', bbox: [0.1, 0.2, 1.4, 0.9] } }),
      ),
    );
    await expect(createInspection(photo)).rejects.toMatchObject({
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
