import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiError } from './services/api';
import {
  createInspection,
  getBatch,
  getBatches,
  getCategories,
  getInspection,
  getInspections,
} from './services/api';
import App from './App';

vi.mock('./services/api', async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    createInspection: vi.fn(),
    getBatch: vi.fn(),
    getBatches: vi.fn(),
    getCategories: vi.fn(),
    getInspection: vi.fn(),
    getInspections: vi.fn(),
  };
});

const CATEGORIES = [
  {
    id: 'bottle',
    displayName: 'Bottle',
    description: 'MVTec AD bottle category',
    defectTypes: ['contamination'],
  },
];

const photo = new File(['photo'], 'bottle.png', { type: 'image/png' });

const DEFECT_RESULT = {
  inspectionId: 'defect123',
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
    reportId: 'defect123',
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

const PASS_RESULT = {
  inspectionId: 'pass123',
  score: 0.2179,
  assessment: {
    verdict: 'pass',
    confidence: 0.7821,
    needsReview: false,
    severity: 'none',
    areaRatio: 0,
    action: 'accept',
    location: null,
  },
  report: {
    reportId: 'pass123',
    generatedAt: '2026-11-18T08:07:19.671664Z',
    persona: 'factory_qc_operator',
    source: 'template',
    manualReviewNotice: null,
    content: {
      summary: 'No defect was found, so the item can be released.',
      findings: ['The anomaly score is below the decision cutoff.'],
      recommendations: ['Accept the item.'],
      defectType: null,
      voiceNoteConflict: null,
    },
  },
};

function renderApp() {
  return render(<App />);
}

async function chooseAndInspect(user) {
  await screen.findByRole('option', { name: 'Bottle' });
  await user.upload(screen.getByLabelText('Choose a photo'), photo);
  await user.click(screen.getByRole('button', { name: 'Inspect photo' }));
}

const HISTORY = {
  items: [
    {
      id: 'insp-001',
      createdAt: '2026-11-20T10:00:00Z',
      category: 'bottle',
      batchId: 'batch-1',
      verdict: 'defect',
      severity: 'high',
      action: 'reject',
      confidence: 0.93,
      thumbnailUrl: '/inspections/insp-001/thumbnail',
      reportPdfAvailable: true,
    },
  ],
  total: 1,
};

beforeEach(() => {
  createInspection.mockReset();
  getBatch.mockReset();
  getBatches.mockReset();
  getCategories.mockReset();
  getInspection.mockReset();
  getInspections.mockReset();
  getCategories.mockResolvedValue(CATEGORIES);
  getBatches.mockResolvedValue([]);
  getBatch.mockResolvedValue({ summary: {}, items: [] });
  getInspections.mockResolvedValue({ items: [], total: 0 });
  getInspection.mockResolvedValue(DEFECT_RESULT);
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true }));
  Element.prototype.scrollIntoView = vi.fn();
  delete document.documentElement.dataset.theme;
  window.localStorage.clear();
});

describe('App', () => {
  it('shows the empty state and the upload flow before any inspection', async () => {
    renderApp();

    expect(screen.getByRole('heading', { name: /no inspection yet/i })).toBeInTheDocument();
    expect(screen.getByText(/upload a photo to get a verdict/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Inspect photo' })).toBeDisabled();
    expect(await screen.findByRole('option', { name: 'Bottle' })).toBeInTheDocument();
  });

  it('runs a real defect flow from photo selection to verdict', async () => {
    createInspection.mockResolvedValue(DEFECT_RESULT);
    const user = userEvent.setup();
    renderApp();

    await chooseAndInspect(user);

    expect((await screen.findAllByText('Reject')).length).toBeGreaterThan(0);
    expect(screen.getAllByText('Defect').length).toBeGreaterThan(0);
    expect(screen.getByText('High')).toBeInTheDocument();
    expect(screen.getByText('defect123')).toBeInTheDocument();
    expect(screen.getByText('AI-written')).toBeInTheDocument();
    expect(
      screen.getByText('A high severity defect covers the lower center of the item.'),
    ).toBeInTheDocument();
    expect(screen.getByText('Flagged area: lower center')).toBeInTheDocument();
    expect(screen.queryByText(/no inspection yet/i)).not.toBeInTheDocument();
    expect(createInspection).toHaveBeenCalledWith(photo);
  });

  it('shows the loading state and disables the inspect action in flight', async () => {
    let resolveRequest;
    createInspection.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveRequest = resolve;
        }),
    );
    const user = userEvent.setup();
    renderApp();

    await chooseAndInspect(user);

    expect(await screen.findByRole('heading', { name: 'Inspecting…' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Inspecting…' })).toBeDisabled();

    await act(async () => {
      resolveRequest(PASS_RESULT);
    });
    expect((await screen.findAllByText('Accept')).length).toBeGreaterThan(0);
  });

  it('shows an API error and lets the operator start over', async () => {
    createInspection.mockRejectedValue(
      new ApiError('The inspection model is unavailable right now. Try again in a moment.', {
        status: 503,
      }),
    );
    const user = userEvent.setup();
    renderApp();

    await chooseAndInspect(user);

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('The inspection did not finish');
    expect(alert).toHaveTextContent('unavailable right now');

    await user.click(screen.getByRole('button', { name: 'Try another photo' }));

    expect(screen.getByText(/no inspection yet/i)).toBeInTheDocument();
    expect(screen.queryByTestId('file-chip')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Inspect photo' })).toBeDisabled();
  });

  it('marks a low-confidence result for manual review', async () => {
    createInspection.mockResolvedValue({
      ...DEFECT_RESULT,
      assessment: {
        ...DEFECT_RESULT.assessment,
        confidence: 0.55,
        needsReview: true,
        action: 're_inspect',
      },
      report: {
        ...DEFECT_RESULT.report,
        manualReviewNotice:
          'This result is close to the decision cutoff. A second operator should review it.',
      },
    });
    const user = userEvent.setup();
    renderApp();

    await chooseAndInspect(user);

    expect((await screen.findAllByText(/needs manual review/i)).length).toBeGreaterThan(0);
    expect(screen.getAllByText('Re-inspect').length).toBeGreaterThan(0);
    expect(screen.getByRole('alert')).toHaveTextContent('Manual review required.');
  });

  it('shows the batch context and refreshes recent inspections after a result', async () => {
    const user = userEvent.setup();
    createInspection.mockResolvedValue({ ...DEFECT_RESULT, batchId: 'batch-9' });
    getBatch.mockResolvedValue({
      summary: {
        batchId: 'batch-9',
        itemCount: 1,
        defectCount: 1,
        passCount: 0,
        reviewCount: 0,
        decision: 'Rejected',
        categories: ['bottle'],
        lastInspectionAt: new Date().toISOString(),
      },
      items: [],
    });
    renderApp();

    await chooseAndInspect(user);

    await waitFor(() => expect(getBatch).toHaveBeenCalledWith('batch-9'));
    expect(await screen.findByText(/1 inspection · 1 defect · 0 reviews/i)).toBeInTheDocument();
    expect(getInspections).toHaveBeenCalledWith({ limit: 6, offset: 0 });
  });

  it('switches to batch history and opens a stored inspection', async () => {
    const user = userEvent.setup();
    getInspections.mockResolvedValue(HISTORY);
    renderApp();

    await user.click(screen.getByRole('button', { name: 'Batches & History' }));
    expect(await screen.findByRole('heading', { name: /inspection history/i })).toBeInTheDocument();

    await user.click(await screen.findByRole('button', { name: 'View' }));
    expect(getInspection).toHaveBeenCalledWith('insp-001');
    expect(await screen.findByRole('heading', { name: 'Inspection result' })).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Close result' }));
    expect(screen.queryByRole('heading', { name: 'Inspection result' })).not.toBeInTheDocument();
  });

  it('opens the shortcut reference and handles the keyboard shortcuts', async () => {
    const isMac = /Mac|iPhone|iPad/i.test(navigator.platform);
    const modifier = isMac ? { metaKey: true } : { ctrlKey: true };
    renderApp();

    fireEvent.keyDown(window, { key: '?' });
    expect(screen.getByRole('dialog', { name: 'Keyboard shortcuts' })).toBeInTheDocument();
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(screen.queryByRole('dialog', { name: 'Keyboard shortcuts' })).not.toBeInTheDocument();

    fireEvent.keyDown(window, { key: 'h', ...modifier });
    expect(await screen.findByRole('heading', { name: /inspection history/i })).toBeInTheDocument();

    fireEvent.keyDown(window, { key: 'k', ...modifier });
    expect(await screen.findByRole('heading', { name: 'New Inspection' })).toBeInTheDocument();
  });

  it('toggles between the light and dark themes', async () => {
    const user = userEvent.setup();
    renderApp();

    expect(document.documentElement.dataset.theme).toBe('light');

    await user.click(screen.getByRole('button', { name: 'Switch to dark theme' }));
    expect(document.documentElement.dataset.theme).toBe('dark');
    expect(window.localStorage.getItem('vdi-theme')).toBe('dark');

    await user.click(screen.getByRole('button', { name: 'Switch to light theme' }));
    expect(document.documentElement.dataset.theme).toBe('light');
  });

  it('retries loading categories after a failure', async () => {
    const user = userEvent.setup();
    getCategories.mockRejectedValueOnce(new Error('Category service offline'));
    renderApp();

    expect((await screen.findAllByText('Category service offline')).length).toBeGreaterThan(0);

    await user.click(screen.getAllByRole('button', { name: 'Retry' })[0]);

    expect(await screen.findByRole('option', { name: 'Bottle' })).toBeInTheDocument();
  });

  it('returns to the inspection tab from the header action', async () => {
    const user = userEvent.setup();
    renderApp();
    await user.click(screen.getByRole('button', { name: 'Batches & History' }));

    await user.click(screen.getByRole('button', { name: '+ New inspection' }));

    expect(await screen.findByRole('heading', { name: 'New Inspection' })).toBeInTheDocument();
  });
});
