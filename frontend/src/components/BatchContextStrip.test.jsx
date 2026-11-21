import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { getBatch } from '../services/api';
import { BatchContextStrip } from './BatchContextStrip';

vi.mock('../services/api', () => ({ getBatch: vi.fn() }));

function summary(overrides = {}) {
  return {
    batchId: 'batch-1',
    itemCount: 4,
    defectCount: 1,
    passCount: 3,
    reviewCount: 0,
    decision: 'Rejected',
    categories: ['bottle'],
    lastInspectionAt: '2026-11-20T10:00:00Z',
    ...overrides,
  };
}

describe('BatchContextStrip', () => {
  beforeEach(() => {
    getBatch.mockReset();
  });

  it('renders nothing without a valid batch id', () => {
    const { container } = render(<BatchContextStrip batchId="bad id!" />);

    expect(container).toBeEmptyDOMElement();
    expect(getBatch).not.toHaveBeenCalled();
  });

  it('loads and shows an existing batch, then opens it', async () => {
    const user = userEvent.setup();
    const onViewBatch = vi.fn();
    getBatch.mockResolvedValue({ summary: summary(), items: [] });

    render(<BatchContextStrip batchId="batch-1" onViewBatch={onViewBatch} />);

    expect(screen.getByText('Checking batch…')).toBeInTheDocument();
    expect(await screen.findByText(/4 inspections · 1 defect · 0 reviews/i)).toBeInTheDocument();
    expect(screen.getByText('Reject')).toBeInTheDocument();
    expect(getBatch).toHaveBeenCalledWith('batch-1');

    await user.click(screen.getByRole('button', { name: 'View batch' }));
    expect(onViewBatch).toHaveBeenCalledWith('batch-1');
  });

  it('says a missing batch is new', async () => {
    const missing = Object.assign(new Error('Batch not found.'), { status: 404 });
    getBatch.mockRejectedValue(missing);

    render(<BatchContextStrip batchId="batch-new" />);

    expect(await screen.findByText(/new batch · no inspections yet/i)).toBeInTheDocument();
  });

  it('reports a batch that cannot be loaded', async () => {
    getBatch.mockRejectedValue(new Error('offline'));

    render(<BatchContextStrip batchId="batch-1" />);

    expect(await screen.findByText(/could not load this batch/i)).toBeInTheDocument();
  });

  it.each([
    ['Passed', 'Pass'],
    ['Needs review', 'Needs review'],
  ])('shows the %s decision', async (decision, label) => {
    getBatch.mockResolvedValue({ summary: summary({ decision, defectCount: 0 }), items: [] });

    render(<BatchContextStrip batchId="batch-1" />);

    expect(await screen.findByText(label)).toBeInTheDocument();
  });
});
