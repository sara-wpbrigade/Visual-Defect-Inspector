import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { ShortcutsModal } from './ShortcutsModal';

describe('ShortcutsModal', () => {
  it('renders nothing while closed', () => {
    const { container } = render(<ShortcutsModal open={false} onClose={vi.fn()} />);

    expect(container).toBeEmptyDOMElement();
  });

  it('lists the shortcuts and closes from the button', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(<ShortcutsModal open onClose={onClose} />);

    expect(screen.getByRole('dialog', { name: 'Keyboard shortcuts' })).toBeInTheDocument();
    expect(screen.getByText('Focus inspection tab')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Close shortcuts' }));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it('closes on Escape and a backdrop click', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    const { container } = render(<ShortcutsModal open onClose={onClose} />);

    await user.keyboard('{Escape}');
    await user.click(container.querySelector('.modal-backdrop'));

    expect(onClose).toHaveBeenCalledTimes(2);
  });
});
