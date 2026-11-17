import { fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { UploadPanel } from './UploadPanel';

function makePhoto(name = 'bottle.png', type = 'image/png', size) {
  const file = new File(['photo-bytes'], name, { type });
  if (size !== undefined) {
    Object.defineProperty(file, 'size', { value: size });
  }
  return file;
}

function renderPanel(overrides = {}) {
  const onInspect = vi.fn();
  const view = render(<UploadPanel onInspect={onInspect} busy={false} {...overrides} />);
  return { onInspect, ...view };
}

describe('UploadPanel', () => {
  it('starts with the inspect action disabled', () => {
    renderPanel();

    expect(screen.getByRole('button', { name: 'Inspect photo' })).toBeDisabled();
    expect(screen.queryByTestId('file-chip')).not.toBeInTheDocument();
    expect(screen.getByText('Take photo')).toBeInTheDocument();
  });

  it('accepts a PNG, previews it and sends it for inspection', async () => {
    const user = userEvent.setup();
    const { onInspect } = renderPanel();
    const photo = makePhoto();

    await user.upload(screen.getByLabelText('Choose a photo'), photo);

    expect(screen.getByTestId('file-chip')).toHaveTextContent('bottle.png');
    expect(screen.getByAltText('Selected bottle photo')).toBeInTheDocument();
    const inspect = screen.getByRole('button', { name: 'Inspect photo' });
    expect(inspect).toBeEnabled();

    await user.click(inspect);

    expect(onInspect).toHaveBeenCalledOnce();
    expect(onInspect).toHaveBeenCalledWith(photo);
  });

  it('rejects an unsupported file before calling the API', async () => {
    const user = userEvent.setup({ applyAccept: false });
    const { onInspect } = renderPanel();

    await user.upload(screen.getByLabelText('Choose a photo'), makePhoto('photo.gif', 'image/gif'));

    expect(screen.getByRole('alert')).toHaveTextContent('Use a JPEG or PNG photo.');
    expect(screen.getByRole('button', { name: 'Inspect photo' })).toBeDisabled();
    expect(onInspect).not.toHaveBeenCalled();
  });

  it('rejects an empty file and a file over the limit', async () => {
    const user = userEvent.setup({ applyAccept: false });
    renderPanel();
    const input = screen.getByLabelText('Choose a photo');

    await user.upload(input, makePhoto('empty.png', 'image/png', 0));
    expect(screen.getByRole('alert')).toHaveTextContent('That file is empty.');

    await user.upload(input, makePhoto('big.png', 'image/png', 11 * 1024 * 1024));
    expect(screen.getByRole('alert')).toHaveTextContent('larger than 10 MB');
  });

  it('accepts a photo dropped onto the dropzone', async () => {
    renderPanel();

    fireEvent.drop(screen.getByTestId('dropzone'), {
      dataTransfer: { files: [makePhoto('dropped.png')] },
    });

    expect(screen.getByTestId('file-chip')).toHaveTextContent('dropped.png');
  });

  it('replaces the preview when a second photo is chosen', async () => {
    const user = userEvent.setup();
    renderPanel();
    vi.mocked(URL.revokeObjectURL).mockClear();
    const input = screen.getByLabelText('Choose a photo');

    await user.upload(input, makePhoto('first.png'));
    await user.upload(input, makePhoto('second.png'));

    expect(URL.revokeObjectURL).toHaveBeenCalledTimes(1);
    expect(screen.getByTestId('file-chip')).toHaveTextContent('second.png');
  });

  it('highlights the dropzone while a file is dragged over it', () => {
    renderPanel();
    const dropzone = screen.getByTestId('dropzone');

    fireEvent.dragOver(dropzone);
    expect(dropzone).toHaveClass('dropzone-active');

    fireEvent.dragLeave(dropzone);
    expect(dropzone).not.toHaveClass('dropzone-active');
  });

  it('opens the picker and the camera from their buttons', async () => {
    const user = userEvent.setup();
    renderPanel();
    const photoClick = vi.spyOn(screen.getByLabelText('Choose a photo'), 'click');
    const cameraClick = vi.spyOn(screen.getByLabelText('Take a photo'), 'click');

    await user.click(screen.getByRole('button', { name: 'Choose photo' }));
    await user.click(screen.getByRole('button', { name: 'Take photo' }));

    expect(photoClick).toHaveBeenCalledOnce();
    expect(cameraClick).toHaveBeenCalledOnce();
  });

  it('disables the actions while an inspection is running', async () => {
    const user = userEvent.setup();
    const { rerender } = render(<UploadPanel onInspect={vi.fn()} busy={false} />);
    await user.upload(screen.getByLabelText('Choose a photo'), makePhoto());
    rerender(<UploadPanel onInspect={vi.fn()} busy />);

    expect(screen.getByRole('button', { name: 'Inspecting…' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Choose photo' })).toBeDisabled();
  });

  it('releases the preview object URL when it unmounts', async () => {
    const user = userEvent.setup();
    vi.mocked(URL.revokeObjectURL).mockClear();
    const { unmount } = renderPanel();
    await user.upload(screen.getByLabelText('Choose a photo'), makePhoto());

    unmount();

    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:preview');
  });
});
