import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { CATEGORY_ERROR_CODES } from '../constants';
import { EmptyState, ErrorBanner, LoadingCard, SkeletonCard } from './StatusPanels';

describe('EmptyState', () => {
  it('explains what the result will contain', () => {
    render(<EmptyState />);

    expect(screen.getByText(/upload a photo to get a verdict/i)).toBeInTheDocument();
    expect(screen.getByText(/straight-on, well-lit photos/i)).toBeInTheDocument();
  });
});

describe('LoadingCard', () => {
  it('announces that the inspection is running', () => {
    render(<LoadingCard />);

    expect(screen.getByRole('status')).toHaveTextContent(/inspecting/i);
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

  it('explains a category mismatch and offers the supported categories', async () => {
    const user = userEvent.setup();
    const onSelectCategory = vi.fn();
    const error = {
      message: 'This photo does not look like a bottle.',
      code: CATEGORY_ERROR_CODES.CATEGORY_MISMATCH,
      supportedCategories: [{ id: 'bottle', display_name: 'Bottle' }],
    };

    render(<ErrorBanner error={error} onReset={vi.fn()} onSelectCategory={onSelectCategory} />);

    expect(screen.getByText('Category Verification Mismatch')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Switch to Bottle' }));
    expect(onSelectCategory).toHaveBeenCalledWith('bottle');
  });

  it('reports the category list loading failure and retries', async () => {
    const user = userEvent.setup();
    const onRetryCategories = vi.fn();
    render(
      <EmptyState
        categoriesError="Could not load categories."
        onRetryCategories={onRetryCategories}
      />,
    );

    expect(screen.getByRole('alert')).toHaveTextContent('Could not load categories.');
    await user.click(screen.getByRole('button', { name: 'Retry' }));
    expect(onRetryCategories).toHaveBeenCalledOnce();
  });
});

describe('SkeletonCard', () => {
  it('renders the placeholder grid', () => {
    const { container } = render(<SkeletonCard />);

    expect(container.querySelector('.skeleton-card')).toBeInTheDocument();
  });
});
