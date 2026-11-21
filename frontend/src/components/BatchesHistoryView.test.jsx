import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import * as api from '../services/api';
import { BatchesHistoryView } from './BatchesHistoryView';

vi.mock('../services/api', () => ({
  getBatches: vi.fn(),
  getBatch: vi.fn(),
  getInspections: vi.fn(),
  exportDefectLogCsv: vi.fn(),
  downloadPdfReport: vi.fn(),
}));

const TODAY = new Date().toISOString();

const MOCK_BATCHES = [
  {
    batchId: 'batch-20261120-01',
    itemCount: 4,
    decision: 'Passed',
    defectCount: 0,
    passCount: 4,
    reviewCount: 0,
    categories: ['bottle'],
    lastInspectionAt: TODAY,
  },
  {
    batchId: 'batch-20261120-02',
    itemCount: 2,
    decision: 'Rejected',
    defectCount: 1,
    passCount: 1,
    reviewCount: 1,
    categories: ['screw'],
    lastInspectionAt: TODAY,
  },
];

const MOCK_ITEMS = [
  {
    id: 'insp-001',
    createdAt: TODAY,
    category: 'bottle',
    batchId: 'batch-20261120-01',
    verdict: 'pass',
    severity: 'none',
    action: 'accept',
    confidence: 0.95,
    needsReview: false,
    thumbnailUrl: '/inspections/insp-001/thumbnail',
    reportPdfAvailable: true,
  },
  {
    id: 'insp-002',
    createdAt: TODAY,
    category: 'screw',
    batchId: 'batch-20261120-02',
    verdict: 'defect',
    severity: 'high',
    action: 'reject',
    confidence: 0.91,
    needsReview: false,
    thumbnailUrl: '/inspections/insp-002/thumbnail',
    reportPdfAvailable: false,
  },
];

const MOCK_INSPECTIONS = { items: MOCK_ITEMS, total: 2 };

function detailFor(batchId) {
  const summary = MOCK_BATCHES.find((batch) => batch.batchId === batchId) ?? MOCK_BATCHES[0];
  return {
    summary,
    items: MOCK_ITEMS.filter((item) => item.batchId === summary.batchId),
  };
}

function historySection() {
  const section = screen.getByRole('heading', { name: /inspection history/i }).closest('section');
  return within(section);
}

describe('BatchesHistoryView', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getBatches.mockResolvedValue(MOCK_BATCHES);
    api.getBatch.mockImplementation((batchId) => Promise.resolve(detailFor(batchId)));
    api.getInspections.mockResolvedValue(MOCK_INSPECTIONS);
  });

  it('renders the KPIs, batch table and history rows', async () => {
    render(<BatchesHistoryView />);

    expect(await screen.findByText('Pass rate')).toBeInTheDocument();
    expect(screen.getByText('83.3%')).toBeInTheDocument();
    expect(screen.getAllByText('batch-20261120-01').length).toBeGreaterThan(0);
    expect(screen.getAllByText('batch-20261120-02').length).toBeGreaterThan(0);
    expect(await screen.findByText(/insp-001/)).toBeInTheDocument();
    expect(screen.getByText(/insp-002/)).toBeInTheDocument();
  });

  it('loads the first batch detail and filters the history from it', async () => {
    const user = userEvent.setup();
    render(<BatchesHistoryView />);

    expect(
      await screen.findByText('4 inspections · 0 defects · 0 need review'),
    ).toBeInTheDocument();
    expect(api.getBatch).toHaveBeenCalledWith('batch-20261120-01');

    await user.click(screen.getByRole('button', { name: 'Filter history' }));

    expect(api.getInspections).toHaveBeenLastCalledWith(
      expect.objectContaining({ batchId: 'batch-20261120-01' }),
    );
  });

  it('selects another batch in the table', async () => {
    const user = userEvent.setup();
    render(<BatchesHistoryView />);
    await screen.findByText('Pass rate');

    await user.click(screen.getByRole('button', { name: 'batch-20261120-02' }));

    expect(api.getBatch).toHaveBeenLastCalledWith('batch-20261120-02');
  });

  it('exports a batch CSV', async () => {
    const user = userEvent.setup();
    render(<BatchesHistoryView />);
    await screen.findByText('Pass rate');

    await user.click(screen.getByRole('button', { name: 'Export batch batch-20261120-01 CSV' }));

    expect(api.exportDefectLogCsv).toHaveBeenCalledWith({
      batchId: 'batch-20261120-01',
      onlyDefects: true,
    });
  });

  it('downloads a PDF from a history row', async () => {
    const user = userEvent.setup();
    render(<BatchesHistoryView />);

    const pdfButtons = await screen.findAllByRole('button', { name: 'PDF' });
    expect(pdfButtons[0]).toBeEnabled();
    expect(pdfButtons[1]).toBeDisabled();

    await user.click(pdfButtons[0]);
    expect(api.downloadPdfReport).toHaveBeenCalledWith('insp-001');
  });

  it('shows empty states when no batches or inspections exist', async () => {
    api.getBatches.mockResolvedValue([]);
    api.getInspections.mockResolvedValue({ items: [], total: 0 });
    render(<BatchesHistoryView />);

    expect(await screen.findByText(/no batches yet/i)).toBeInTheDocument();
    expect(screen.getByText(/no inspections match your filters/i)).toBeInTheDocument();
    expect(screen.getByText(/select a batch to see its inspections/i)).toBeInTheDocument();
  });

  it('shows load errors for batches and history', async () => {
    api.getBatches.mockRejectedValue(new Error('Batch service down'));
    api.getInspections.mockRejectedValue(new Error('History service down'));
    render(<BatchesHistoryView />);

    expect(await screen.findByText('Batch service down')).toBeInTheDocument();
    expect(screen.getByText('History service down')).toBeInTheDocument();
  });

  it('exports the whole defect log with the active filters', async () => {
    const user = userEvent.setup();
    render(<BatchesHistoryView />);
    await screen.findByText('Pass rate');
    const history = historySection();

    await user.type(history.getByLabelText('Batch:'), 'batch-20261120-01');
    await user.selectOptions(history.getByLabelText('Category:'), 'screw');
    await user.click(history.getByRole('button', { name: 'Export CSV' }));

    expect(api.exportDefectLogCsv).toHaveBeenCalledWith({
      batchId: 'batch-20261120-01',
      category: 'screw',
      onlyDefects: true,
    });
    expect(await screen.findByText('Exported defect log CSV.')).toBeInTheDocument();
  });

  it('shows an error toast when an export fails', async () => {
    const user = userEvent.setup();
    api.exportDefectLogCsv.mockRejectedValue(new Error('server busy'));
    render(<BatchesHistoryView />);
    await screen.findByText('Pass rate');

    await user.click(screen.getByRole('button', { name: 'Export batch batch-20261120-01 CSV' }));

    expect(await screen.findByText(/export failed: server busy/i)).toBeInTheDocument();
  });

  it('pages through a longer history', async () => {
    const user = userEvent.setup();
    api.getInspections.mockResolvedValue({ items: MOCK_ITEMS, total: 45 });
    render(<BatchesHistoryView />);

    await user.click(await screen.findByRole('button', { name: 'Next' }));
    expect(api.getInspections).toHaveBeenLastCalledWith(expect.objectContaining({ offset: 20 }));

    await user.click(screen.getByRole('button', { name: 'Previous' }));
    expect(api.getInspections).toHaveBeenLastCalledWith(expect.objectContaining({ offset: 0 }));
  });

  it('labels a batch that needs review', async () => {
    api.getBatches.mockResolvedValue([
      {
        ...MOCK_BATCHES[0],
        decision: 'Needs review',
        reviewCount: 1,
      },
    ]);
    api.getBatch.mockResolvedValue({
      summary: { ...MOCK_BATCHES[0], decision: 'Needs review', reviewCount: 1 },
      items: [MOCK_ITEMS[0]],
    });
    render(<BatchesHistoryView />);

    expect((await screen.findAllByText('Needs review')).length).toBeGreaterThan(0);
  });

  it('refreshes batches, today count and history', async () => {
    const user = userEvent.setup();
    render(<BatchesHistoryView />);
    await screen.findByText('Pass rate');

    await user.click(screen.getByRole('button', { name: 'Refresh' }));

    expect(api.getBatches).toHaveBeenCalledTimes(2);
    // Two inspection requests per load: the Today KPI and the history table.
    expect(api.getInspections).toHaveBeenCalledTimes(4);
  });
});
