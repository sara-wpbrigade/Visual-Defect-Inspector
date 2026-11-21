import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { ErrorBoundary } from './ErrorBoundary';

function Exploding({ shouldThrow }) {
  if (shouldThrow) {
    throw new Error('Render exploded');
  }
  return <p>Recovered</p>;
}

describe('ErrorBoundary', () => {
  it('shows the recovery card and dismisses the error', async () => {
    const user = userEvent.setup();
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});
    vi.stubGlobal('reportError', vi.fn());

    const { rerender } = render(
      <ErrorBoundary>
        <Exploding shouldThrow />
      </ErrorBoundary>,
    );

    expect(screen.getByRole('alert')).toHaveTextContent('Render exploded');
    expect(consoleError).toHaveBeenCalled();

    rerender(
      <ErrorBoundary>
        <Exploding shouldThrow={false} />
      </ErrorBoundary>,
    );
    await user.click(screen.getByRole('button', { name: 'Dismiss' }));

    expect(screen.getByText('Recovered')).toBeInTheDocument();
  });

  it('renders its children when nothing throws', () => {
    render(
      <ErrorBoundary>
        <p>All good</p>
      </ErrorBoundary>,
    );

    expect(screen.getByText('All good')).toBeInTheDocument();
  });
});
