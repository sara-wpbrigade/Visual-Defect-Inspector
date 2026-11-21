import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { getInspections } from '../services/api';
import { RecentInspections } from './RecentInspections';

vi.mock('../services/api', () => ({ getInspections: vi.fn() }));

const ITEMS = [
  {
    id: 'insp-001',
    createdAt: new Date().toISOString(),
    category: 'bottle',
    verdict: 'pass',
    action: 'accept',
    thumbnailUrl: '/inspections/insp-001/thumbnail',
  },
  {
    id: 'insp-002',
    createdAt: new Date().toISOString(),
    category: 'screw',
    verdict: 'defect',
    action: 'reject',
    thumbnailUrl: null,
  },
];

describe('RecentInspections', () => {
  beforeEach(() => {
    getInspections.mockReset();
  });

  it('shows recent items and opens one', async () => {
    const user = userEvent.setup();
    const onSelectInspection = vi.fn();
    getInspections.mockResolvedValue({ items: ITEMS, total: 2 });

    render(<RecentInspections onSelectInspection={onSelectInspection} />);

    expect(await screen.findByText('bottle')).toBeInTheDocument();
    expect(screen.getByText('screw')).toBeInTheDocument();
    expect(getInspections).toHaveBeenCalledWith({ limit: 6, offset: 0 });

    await user.click(screen.getByRole('button', { name: /bottle/i }));
    expect(onSelectInspection).toHaveBeenCalledWith('insp-001');
  });

  it('offers a link to the full history', async () => {
    const user = userEvent.setup();
    const onViewAll = vi.fn();
    getInspections.mockResolvedValue({ items: ITEMS, total: 2 });

    render(<RecentInspections onViewAll={onViewAll} />);
    await screen.findByText('bottle');

    await user.click(screen.getByRole('button', { name: 'View all' }));
    expect(onViewAll).toHaveBeenCalledOnce();
  });

  it('shows the empty state', async () => {
    getInspections.mockResolvedValue({ items: [], total: 0 });

    render(<RecentInspections />);

    expect(await screen.findByText(/no inspections yet/i)).toBeInTheDocument();
  });

  it('shows a load error', async () => {
    getInspections.mockRejectedValue(new Error('History offline'));

    render(<RecentInspections />);

    expect(await screen.findByRole('alert')).toHaveTextContent('History offline');
  });

  it('reloads when the refresh key changes', async () => {
    getInspections.mockResolvedValue({ items: ITEMS, total: 2 });
    const { rerender } = render(<RecentInspections refreshKey={0} />);
    await screen.findByText('bottle');

    rerender(<RecentInspections refreshKey={1} />);

    expect(getInspections).toHaveBeenCalledTimes(2);
  });
});
