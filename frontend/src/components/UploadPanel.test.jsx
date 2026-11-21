import { fireEvent, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { UploadPanel } from './UploadPanel';

afterEach(() => {
  delete window.navigator.mediaDevices;
});

const OTHER_CATEGORY = {
  id: 'screw',
  displayName: 'Screw',
  description: 'MVTec AD screw category',
  defectTypes: ['thread damage'],
};

function makePhoto(name = 'bottle.png', type = 'image/png', size) {
  const file = new File(['photo-bytes'], name, { type });
  if (size !== undefined) {
    Object.defineProperty(file, 'size', { value: size });
  }
  return file;
}

const CATEGORIES = [
  {
    id: 'bottle',
    displayName: 'Bottle',
    description: 'MVTec AD bottle category',
    defectTypes: ['contamination'],
  },
];

function renderPanel(overrides = {}) {
  const onInspect = vi.fn();
  const view = render(
    <UploadPanel
      onInspect={onInspect}
      busy={false}
      categories={CATEGORIES}
      selectedCategory="bottle"
      onSelectCategory={vi.fn()}
      {...overrides}
    />,
  );
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
    const { rerender } = render(
      <UploadPanel
        onInspect={vi.fn()}
        busy={false}
        categories={CATEGORIES}
        selectedCategory="bottle"
      />,
    );
    await user.upload(screen.getByLabelText('Choose a photo'), makePhoto());
    rerender(
      <UploadPanel onInspect={vi.fn()} busy categories={CATEGORIES} selectedCategory="bottle" />,
    );

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

  it('validates the optional batch id before allowing an inspection', async () => {
    const user = userEvent.setup();
    renderPanel();
    await user.upload(screen.getByLabelText('Choose a photo'), makePhoto());
    const batchInput = screen.getByLabelText(/batch id/i);

    await user.type(batchInput, 'bad id!');

    expect(screen.getByRole('alert')).toHaveTextContent('Use up to 40 characters');
    expect(screen.getByRole('button', { name: 'Inspect photo' })).toBeDisabled();

    await user.clear(batchInput);
    await user.type(batchInput, 'batch-1');

    expect(screen.getByRole('button', { name: 'Inspect photo' })).toBeEnabled();
  });

  it('reports batch id changes to the parent', async () => {
    const user = userEvent.setup();
    const onBatchIdChange = vi.fn();
    renderPanel({ onBatchIdChange });

    await user.type(screen.getByLabelText(/batch id/i), 'batch-1');

    expect(onBatchIdChange).toHaveBeenLastCalledWith('batch-1');
  });

  it('forwards the selected category and batch id', async () => {
    const user = userEvent.setup();
    const onSelectCategory = vi.fn();
    const { onInspect } = renderPanel({
      categories: [CATEGORIES[0], OTHER_CATEGORY],
      selectedCategory: 'bottle',
      onSelectCategory,
    });
    const photo = makePhoto();

    await user.selectOptions(screen.getByLabelText('Inspection Category'), 'screw');
    expect(onSelectCategory).toHaveBeenCalledWith('screw');

    await user.upload(screen.getByLabelText('Choose a photo'), photo);
    await user.type(screen.getByLabelText(/batch id/i), 'batch-1');
    await user.click(screen.getByRole('button', { name: 'Inspect photo' }));

    expect(onInspect).toHaveBeenCalledWith(photo, {
      category: 'bottle',
      batchId: 'batch-1',
      voiceNote: null,
    });
  });

  it('attaches, previews and removes an uploaded voice note', async () => {
    const user = userEvent.setup();
    const { container } = renderPanel();
    await user.click(screen.getByRole('button', { name: /optional voice note/i }));
    const audio = new File(['audio-bytes'], 'note.wav', { type: 'audio/wav' });

    await user.upload(screen.getByLabelText('Upload audio voice note'), audio);

    expect(screen.getByText('note.wav')).toBeInTheDocument();
    expect(screen.getByText(/voice note attached/i)).toBeInTheDocument();
    expect(container.querySelector('audio')).toHaveAttribute('src', 'blob:preview');

    await user.click(screen.getByRole('button', { name: 'Remove note' }));

    expect(screen.queryByText('note.wav')).not.toBeInTheDocument();
    expect(screen.queryByText(/voice note attached/i)).not.toBeInTheDocument();
  });

  it('rejects empty, oversized and unsupported audio files', async () => {
    const user = userEvent.setup({ applyAccept: false });
    renderPanel();
    await user.click(screen.getByRole('button', { name: /optional voice note/i }));
    const input = screen.getByLabelText('Upload audio voice note');

    await user.upload(input, new File([], 'empty.wav', { type: 'audio/wav' }));
    expect(screen.getByRole('alert')).toHaveTextContent('That audio file is empty.');

    const big = new File(['audio'], 'big.wav', { type: 'audio/wav' });
    Object.defineProperty(big, 'size', { value: 6 * 1024 * 1024 });
    await user.upload(input, big);
    expect(screen.getByRole('alert')).toHaveTextContent('Audio file must be under 5 MB.');

    await user.upload(input, new File(['audio'], 'note.txt', { type: 'text/plain' }));
    expect(screen.getByRole('alert')).toHaveTextContent('Use an audio file in WAV');
  });

  it('explains when recording is unsupported', async () => {
    const user = userEvent.setup();
    renderPanel();
    await user.click(screen.getByRole('button', { name: /optional voice note/i }));

    await user.click(screen.getByRole('button', { name: 'Record voice note' }));

    expect(screen.getByRole('alert')).toHaveTextContent(
      'Audio recording is not supported in this browser.',
    );
  });

  it('explains a denied microphone permission', async () => {
    const user = userEvent.setup();
    Object.defineProperty(window.navigator, 'mediaDevices', {
      configurable: true,
      value: { getUserMedia: vi.fn().mockRejectedValue(new Error('denied')) },
    });
    renderPanel();
    await user.click(screen.getByRole('button', { name: /optional voice note/i }));

    await user.click(screen.getByRole('button', { name: 'Record voice note' }));

    expect(screen.getByRole('alert')).toHaveTextContent(
      'Microphone permission was denied or microphone is unavailable.',
    );
  });

  it('records a voice note and stops at the operator request', async () => {
    const user = userEvent.setup();
    class FakeMediaRecorder {
      constructor() {
        this.state = 'inactive';
        this.mimeType = 'audio/webm';
      }

      start() {
        this.state = 'recording';
      }

      stop() {
        this.state = 'inactive';
        this.ondataavailable?.({ data: new Blob(['audio']) });
        this.onstop?.();
      }
    }
    const track = { stop: vi.fn() };
    Object.defineProperty(window.navigator, 'mediaDevices', {
      configurable: true,
      value: {
        getUserMedia: vi.fn().mockResolvedValue({ getTracks: () => [track] }),
      },
    });
    vi.stubGlobal('MediaRecorder', FakeMediaRecorder);
    renderPanel();
    await user.click(screen.getByRole('button', { name: /optional voice note/i }));

    await user.click(screen.getByRole('button', { name: 'Record voice note' }));
    expect(screen.getByRole('button', { name: /stop recording/i })).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: /stop recording/i }));

    expect(screen.getByText('voice-note.webm')).toBeInTheDocument();
    expect(track.stop).toHaveBeenCalledOnce();
  });
});
