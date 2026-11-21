import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { ResultModal } from './ResultModal';

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
    location: { region: 'lower center', bbox: [0.1, 0.2, 0.3, 0.4] },
  },
  report: {
    reportId: 'abc123',
    generatedAt: '2026-11-18T08:07:19.671664Z',
    persona: 'factory_qc_operator',
    source: 'ai',
    manualReviewNotice: null,
    content: {
      summary: 'A defect was found.',
      findings: ['The item is damaged.'],
      recommendations: ['Reject the item.'],
      defectType: 'contamination',
      voiceNoteConflict: null,
    },
  },
};

describe('ResultModal', () => {
  it('shows the loading card while a result is fetched', () => {
    render(<ResultModal loading onClose={vi.fn()} />);

    expect(screen.getByRole('heading', { name: 'Inspecting…' })).toBeInTheDocument();
  });

  it('shows an error with a close button', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(<ResultModal error="Could not load it." onClose={onClose} />);

    expect(screen.getByRole('alert')).toHaveTextContent('Could not load it.');
    await user.click(screen.getByRole('button', { name: 'Close' }));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it('renders the stored result and forwards reset', async () => {
    const user = userEvent.setup();
    const onReset = vi.fn();
    render(<ResultModal result={RESULT} onClose={vi.fn()} onReset={onReset} />);

    expect(screen.getByText('A defect was found.')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Inspect another photo' }));
    expect(onReset).toHaveBeenCalledOnce();
  });

  it('closes on the close button, Escape and a backdrop click', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    const { container } = render(<ResultModal result={RESULT} onClose={onClose} />);

    await user.click(screen.getByRole('button', { name: 'Close result' }));
    await user.keyboard('{Escape}');
    await user.click(container.querySelector('.modal-backdrop'));

    expect(onClose).toHaveBeenCalledTimes(3);
  });
});
