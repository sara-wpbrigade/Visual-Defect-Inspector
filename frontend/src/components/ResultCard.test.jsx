import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { ResultCard } from './ResultCard';

const PASS_RESULT = {
  inspectionId: 'pass001',
  score: 0.2179,
  assessment: {
    verdict: 'pass',
    confidence: 0.7821,
    needsReview: false,
    severity: 'none',
    areaRatio: 0,
    action: 'accept',
  },
};

const REJECT_RESULT = {
  inspectionId: 'defect001',
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

const REVIEW_RESULT = {
  inspectionId: 'review001',
  score: 0.55,
  assessment: {
    verdict: 'defect',
    confidence: 0.55,
    needsReview: true,
    severity: 'low',
    areaRatio: 0.0093,
    action: 're_inspect',
  },
};

describe('ResultCard', () => {
  it('shows a pass with its confidence, severity and recommended action', () => {
    render(<ResultCard result={PASS_RESULT} onReset={vi.fn()} />);

    expect(screen.getByText('Pass')).toBeInTheDocument();
    expect(screen.getByText('Accept')).toBeInTheDocument();
    expect(screen.getByText('78.2%')).toBeInTheDocument();
    expect(screen.getByText('None')).toBeInTheDocument();
    expect(screen.getByText('0.218')).toBeInTheDocument();
    expect(screen.getByText('pass001')).toBeInTheDocument();
    expect(screen.queryByText(/needs manual review/i)).not.toBeInTheDocument();
  });

  it('shows a high severity defect as a reject', () => {
    render(<ResultCard result={REJECT_RESULT} onReset={vi.fn()} />);

    expect(screen.getByText('Defect')).toBeInTheDocument();
    expect(screen.getByText('Reject')).toBeInTheDocument();
    expect(screen.getByText('High')).toBeInTheDocument();
    expect(screen.getByText('17.5%')).toBeInTheDocument();
    expect(screen.getByText('93.7%')).toBeInTheDocument();
  });

  it('flags a borderline score as needing manual review', () => {
    render(<ResultCard result={REVIEW_RESULT} onReset={vi.fn()} />);

    expect(screen.getByText(/needs manual review/i)).toBeInTheDocument();
    expect(screen.getByText('Re-inspect')).toBeInTheDocument();
  });

  it('falls back to raw enum values when the API adds a new one', () => {
    render(
      <ResultCard
        result={{
          ...PASS_RESULT,
          assessment: {
            ...PASS_RESULT.assessment,
            verdict: 'unknown',
            severity: 'critical',
            action: 'escalate',
          },
        }}
        onReset={vi.fn()}
      />,
    );

    expect(screen.getByText('unknown')).toBeInTheDocument();
    expect(screen.getByText('critical')).toBeInTheDocument();
    expect(screen.getByText('escalate')).toBeInTheDocument();
    expect(screen.getByText(/standard procedure/i)).toBeInTheDocument();
  });

  it('offers a fresh inspection and forwards the reset', async () => {
    const user = userEvent.setup();
    const onReset = vi.fn();
    render(<ResultCard result={PASS_RESULT} onReset={onReset} />);

    await user.click(screen.getByRole('button', { name: 'Inspect another photo' }));

    expect(onReset).toHaveBeenCalledOnce();
  });
});
