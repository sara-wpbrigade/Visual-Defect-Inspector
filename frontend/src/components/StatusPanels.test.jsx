import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { EmptyState, ErrorBanner, LoadingCard } from './StatusPanels';

describe('EmptyState', () => {
  it('explains what the result will contain', () => {
    render(<EmptyState />);

    expect(screen.getByText(/your result will appear here/i)).toBeInTheDocument();
    expect(screen.getByText(/straight-on, well-lit photos/i)).toBeInTheDocument();
  });
});

describe('LoadingCard', () => {
  it('announces that the inspection is running', () => {
    render(<LoadingCard />);

    expect(screen.getByRole('status')).toHaveTextContent(/inspecting photo/i);
  });
});

describe('ErrorBanner', () => {
  it('shows the API message and forwards the reset', async () => {
    const user = userEvent.setup();
    const onReset = vi.fn();
    render(<ErrorBanner error={new Error('Model unavailable')} onReset={onReset} />);

    expect(screen.getByRole('alert')).toHaveTextContent('Model unavailable');
    await user.click(screen.getByRole('button', { name: 'Try another photo' }));
    expect(onReset).toHaveBeenCalledOnce();
  });

  it('has a safe fallback when no error object is passed', () => {
    render(<ErrorBanner error={null} onReset={vi.fn()} />);

    expect(screen.getByRole('alert')).toHaveTextContent('Unknown error.');
  });
});
