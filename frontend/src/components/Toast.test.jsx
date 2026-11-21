import { act, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { Toast } from './Toast';

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
});

describe('Toast', () => {
  it('shows the message with its tone and dismisses on click', () => {
    const onClose = vi.fn();
    render(<Toast message="Saved" tone="success" onClose={onClose} />);

    const toast = screen.getByRole('status');
    expect(toast).toHaveTextContent('Saved');
    expect(toast).toHaveClass('toast-success');

    fireEvent.click(screen.getByRole('button', { name: 'Dismiss' }));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it('auto-dismisses after the duration', () => {
    const onClose = vi.fn();
    render(<Toast message="Saved" onClose={onClose} duration={1000} />);

    act(() => {
      vi.advanceTimersByTime(1000);
    });

    expect(onClose).toHaveBeenCalledOnce();
  });
});
