import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  GENERIC_ERROR_MESSAGE,
  MAX_IMAGE_MEGABYTES,
  NETWORK_ERROR_MESSAGE,
  UNEXPECTED_RESPONSE_MESSAGE,
} from '../constants';
import {
  ApiError,
  createInspection,
  downloadPdfReport,
  exportDefectLogCsv,
  getBatch,
  getBatches,
  getCategories,
  getInspection,
  getInspections,
} from './api';

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

function fileResponse(status = 200, blob = new Blob(['file'])) {
  return {
    ok: status >= 200 && status < 300,
    status,
    blob: async () => blob,
    json: async () => {
      throw new SyntaxError('not JSON');
    },
  };
}

const HISTORY_ITEM = {
  id: 'abc123',
  created_at: '2026-11-20T10:00:00Z',
  category: 'bottle',
  batch_id: 'batch-1',
  verdict: 'pass',
  severity: 'none',
  action: 'accept',
  confidence: 0.95,
  needs_review: false,
  thumbnail_url: '/inspections/abc123/thumbnail',
  batch_decision: 'Passed',
  report_pdf_available: true,
  report_pdf_url: '/inspections/abc123/report.pdf',
};

const BATCH_SUMMARY = {
  batch_id: 'batch-1',
  item_count: 2,
  decision: 'Passed',
  defect_count: 1,
  pass_count: 1,
  review_count: 0,
  categories: ['bottle'],
  last_inspection_at: '2026-11-20T10:00:00Z',
};

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
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

  it('maps an optional voice note and its transcript', async () => {
    stubFetch(
      jsonResponse(201, {
        ...API_PAYLOAD,
        voice_note: {
          status: 'transcribed',
          text: 'spots after the rain',
          language: 'en',
          duration_seconds: 2.5,
          truncated: false,
        },
      }),
    );

    const result = await createInspection(photo);

    expect(result.voiceNote).toEqual({
      status: 'transcribed',
      text: 'spots after the rain',
      language: 'en',
      durationSeconds: 2.5,
      truncated: false,
    });
  });

  it('rejects a malformed voice-note block', async () => {
    stubFetch(
      jsonResponse(201, {
        ...API_PAYLOAD,
        voice_note: {
          status: 'unknown',
          text: 'oops',
          language: 'en',
          duration_seconds: 1,
          truncated: false,
        },
      }),
    );

    await expect(createInspection(photo)).rejects.toMatchObject({
      message: UNEXPECTED_RESPONSE_MESSAGE,
    });
  });

  it('shows the server detail when a voice note is unusable', async () => {
    stubFetch(
      jsonResponse(400, { detail: 'Unsupported audio format; use WAV, MP3, OGG, WebM or M4A.' }),
    );

    await expect(createInspection(photo)).rejects.toMatchObject({
      status: 400,
      message: expect.stringContaining('Unsupported audio'),
    });
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

describe('getCategories', () => {
  it('maps the category list to camelCase', async () => {
    stubFetch(
      jsonResponse(200, [
        {
          id: 'bottle',
          display_name: 'Bottle',
          description: 'A bottle',
          defect_types: ['contamination'],
        },
      ]),
    );

    await expect(getCategories()).resolves.toEqual([
      {
        id: 'bottle',
        displayName: 'Bottle',
        description: 'A bottle',
        defectTypes: ['contamination'],
      },
    ]);
  });

  it('falls back for a missing display name and defect list', async () => {
    stubFetch(jsonResponse(200, [{ id: 'screw' }]));

    await expect(getCategories()).resolves.toEqual([
      { id: 'screw', displayName: 'screw', description: '', defectTypes: [] },
    ]);
  });

  it('rejects a non-array body', async () => {
    stubFetch(jsonResponse(200, { items: [] }));

    await expect(getCategories()).rejects.toMatchObject({
      message: UNEXPECTED_RESPONSE_MESSAGE,
    });
  });

  it('maps network and HTTP failures', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('down')));
    await expect(getCategories()).rejects.toMatchObject({
      status: 0,
      message: NETWORK_ERROR_MESSAGE,
    });

    stubFetch(jsonResponse(503, { detail: 'unavailable' }));
    await expect(getCategories()).rejects.toMatchObject({ status: 503 });
  });
});

describe('getBatches', () => {
  it('maps batch summaries and sends paging parameters', async () => {
    const fetchMock = stubFetch(jsonResponse(200, [BATCH_SUMMARY]));

    await expect(getBatches({ limit: 5, offset: 10 })).resolves.toEqual([
      {
        batchId: 'batch-1',
        itemCount: 2,
        decision: 'Passed',
        defectCount: 1,
        passCount: 1,
        reviewCount: 0,
        categories: ['bottle'],
        lastInspectionAt: '2026-11-20T10:00:00Z',
      },
    ]);
    expect(fetchMock.mock.calls[0][0]).toBe('/batches?limit=5&offset=10');
  });

  it('tolerates a missing category list', async () => {
    stubFetch(jsonResponse(200, [{ ...BATCH_SUMMARY, categories: undefined }]));

    const [batch] = await getBatches();
    expect(batch.categories).toEqual([]);
  });

  it('rejects a non-array body and network failures', async () => {
    stubFetch(jsonResponse(200, {}));
    await expect(getBatches()).rejects.toMatchObject({
      message: UNEXPECTED_RESPONSE_MESSAGE,
    });

    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('down')));
    await expect(getBatches()).rejects.toMatchObject({ status: 0 });
  });
});

describe('getBatch', () => {
  it('maps the summary and item rows', async () => {
    stubFetch(
      jsonResponse(200, {
        summary: BATCH_SUMMARY,
        items: [HISTORY_ITEM],
      }),
    );

    const result = await getBatch('batch-1');

    expect(result.summary).toMatchObject({
      batchId: 'batch-1',
      itemCount: 2,
      passCount: 1,
      reviewCount: 0,
      categories: ['bottle'],
      lastInspectionAt: '2026-11-20T10:00:00Z',
    });
    expect(result.items[0]).toMatchObject({
      id: 'abc123',
      verdict: 'pass',
      reportPdfAvailable: true,
    });
  });

  it('uses empty defaults for a partial summary', async () => {
    stubFetch(jsonResponse(200, { summary: { batch_id: 'batch-2' }, items: null }));

    const result = await getBatch('batch-2');

    expect(result.summary.batchId).toBe('batch-2');
    expect(result.summary.categories).toEqual([]);
    expect(result.summary.lastInspectionAt).toBeUndefined();
    expect(result.items).toEqual([]);
  });

  it('maps HTTP and network failures', async () => {
    stubFetch(jsonResponse(404, { detail: 'Batch not found.' }));
    await expect(getBatch('missing')).rejects.toMatchObject({ status: 404 });

    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('down')));
    await expect(getBatch('batch-1')).rejects.toMatchObject({ status: 0 });
  });
});

describe('getInspections', () => {
  it('maps history rows and appends filters', async () => {
    const fetchMock = stubFetch(jsonResponse(200, { items: [HISTORY_ITEM], total: 7 }));

    const result = await getInspections({
      limit: 5,
      offset: 10,
      batchId: 'batch-1',
      category: 'bottle',
    });

    expect(fetchMock.mock.calls[0][0]).toBe(
      '/inspections?limit=5&offset=10&batch_id=batch-1&category=bottle',
    );
    expect(result.total).toBe(7);
    expect(result.items[0]).toMatchObject({
      id: 'abc123',
      thumbnailUrl: '/inspections/abc123/thumbnail',
      batchDecision: 'Passed',
      reportPdfAvailable: true,
    });
  });

  it('falls back to the item count and omits empty filters', async () => {
    const fetchMock = stubFetch(jsonResponse(200, { items: [HISTORY_ITEM] }));

    const result = await getInspections();

    expect(fetchMock.mock.calls[0][0]).toBe('/inspections?limit=20&offset=0');
    expect(result.total).toBe(1);
  });

  it('uses empty lists and derived URLs when rows are partial', async () => {
    stubFetch(
      jsonResponse(200, {
        items: [{ inspection_id: 'def456', assessment: { verdict: 'defect' } }],
      }),
    );

    const result = await getInspections();

    expect(result.items[0]).toMatchObject({
      id: 'def456',
      verdict: 'defect',
      thumbnailUrl: '/inspections/def456/thumbnail',
      reportPdfAvailable: false,
    });
  });

  it('maps HTTP and network failures', async () => {
    stubFetch(jsonResponse(500, { detail: 'boom' }));
    await expect(getInspections()).rejects.toMatchObject({ status: 500 });

    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('down')));
    await expect(getInspections()).rejects.toMatchObject({ status: 0 });
  });
});

describe('getInspection', () => {
  it('normalizes one stored inspection', async () => {
    stubFetch(
      jsonResponse(200, {
        ...API_PAYLOAD,
        inspection_id: 'abc123',
        category: 'bottle',
        created_at: '2026-11-20T10:00:00Z',
        batch_id: 'batch-1',
        batch_decision: 'Rejected',
        report_pdf_available: true,
        report_pdf_url: '/inspections/abc123/report.pdf',
        images: {
          photo: '/inspections/abc123/photo',
          overlay: '/inspections/abc123/overlay',
          thumbnail: '/inspections/abc123/thumbnail',
        },
      }),
    );

    const result = await getInspection('abc123');

    expect(result).toMatchObject({
      inspectionId: 'abc123',
      category: 'bottle',
      batchDecision: 'Rejected',
      reportPdfAvailable: true,
      images: {
        photo: '/inspections/abc123/photo',
        overlay: '/inspections/abc123/overlay',
        thumbnail: '/inspections/abc123/thumbnail',
      },
    });
  });

  it('maps HTTP and network failures', async () => {
    stubFetch(jsonResponse(404, { detail: 'not found' }));
    await expect(getInspection('missing')).rejects.toMatchObject({ status: 404 });

    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('down')));
    await expect(getInspection('abc123')).rejects.toMatchObject({ status: 0 });
  });
});

describe('downloadPdfReport', () => {
  it('downloads the PDF and triggers a browser download', async () => {
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    const fetchMock = stubFetch(fileResponse(200));

    await downloadPdfReport('abc123');

    expect(fetchMock.mock.calls[0][0]).toBe('/inspections/abc123/report.pdf');
    expect(click).toHaveBeenCalledOnce();
  });

  it('maps HTTP and network failures', async () => {
    stubFetch(fileResponse(404));
    await expect(downloadPdfReport('missing')).rejects.toMatchObject({ status: 404 });

    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('down')));
    await expect(downloadPdfReport('abc123')).rejects.toMatchObject({ status: 0 });
  });
});

describe('exportDefectLogCsv', () => {
  it('downloads a CSV with the selected filters', async () => {
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    const fetchMock = stubFetch(fileResponse(200, new Blob(['id\n'])));

    await exportDefectLogCsv({ batchId: 'batch-1', category: 'bottle', onlyDefects: false });

    expect(fetchMock.mock.calls[0][0]).toBe(
      '/inspections/export.csv?batch_id=batch-1&category=bottle&only_defects=false',
    );
    expect(click).toHaveBeenCalledOnce();
  });

  it('uses only_defects by default', async () => {
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
    const fetchMock = stubFetch(fileResponse(200));

    await exportDefectLogCsv();

    expect(fetchMock.mock.calls[0][0]).toBe('/inspections/export.csv?only_defects=true');
  });

  it('maps HTTP and network failures', async () => {
    stubFetch(fileResponse(500));
    await expect(exportDefectLogCsv()).rejects.toMatchObject({ status: 500 });

    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('down')));
    await expect(exportDefectLogCsv()).rejects.toMatchObject({ status: 0 });
  });
});
