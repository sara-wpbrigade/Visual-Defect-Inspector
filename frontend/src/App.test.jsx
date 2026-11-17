import { act, render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiError } from './services/api';
import { createInspection } from './services/api';
import App from './App';

vi.mock('./services/api', async (importOriginal) => {
  const actual = await importOriginal();
  return { ...actual, createInspection: vi.fn() };
});

const photo = new File(['photo'], 'bottle.png', { type: 'image/png' });

const DEFECT_RESULT = {
  inspectionId: 'defect123',
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

const PASS_RESULT = {
  inspectionId: 'pass123',
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

function renderApp() {
  return render(<App />);
}

async function chooseAndInspect(user) {
  await user.upload(screen.getByLabelText('Choose a photo'), photo);
  await user.click(screen.getByRole('button', { name: 'Inspect photo' }));
}

beforeEach(() => {
  createInspection.mockReset();
});

describe('App', () => {
  it('shows the empty state and the upload flow before any inspection', () => {
    renderApp();

    expect(screen.getByRole('heading', { name: /bottle qc in one photo/i })).toBeInTheDocument();
    expect(screen.getByText(/your result will appear here/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Inspect photo' })).toBeDisabled();
  });

  it('runs a real defect flow from photo selection to verdict', async () => {
    createInspection.mockResolvedValue(DEFECT_RESULT);
    const user = userEvent.setup();
    renderApp();

    await chooseAndInspect(user);

    expect(await screen.findByText('Reject')).toBeInTheDocument();
    expect(screen.getByText('Defect')).toBeInTheDocument();
    expect(screen.getByText('High')).toBeInTheDocument();
    expect(screen.getByText('defect123')).toBeInTheDocument();
    expect(screen.queryByText(/your result will appear here/i)).not.toBeInTheDocument();
    expect(createInspection).toHaveBeenCalledWith(photo);
  });

  it('shows the loading state and disables the inspect action in flight', async () => {
    let resolveRequest;
    createInspection.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveRequest = resolve;
        }),
    );
    const user = userEvent.setup();
    renderApp();

    await chooseAndInspect(user);

    expect(await screen.findByText(/inspecting photo/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Inspecting…' })).toBeDisabled();

    await act(async () => {
      resolveRequest(PASS_RESULT);
    });
    expect(await screen.findByText('Accept')).toBeInTheDocument();
  });

  it('shows an API error and lets the operator start over', async () => {
    createInspection.mockRejectedValue(
      new ApiError('The inspection model is unavailable right now. Try again in a moment.', {
        status: 503,
      }),
    );
    const user = userEvent.setup();
    renderApp();

    await chooseAndInspect(user);

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('The inspection did not finish');
    expect(alert).toHaveTextContent('unavailable right now');

    await user.click(screen.getByRole('button', { name: 'Try another photo' }));

    expect(screen.getByText(/your result will appear here/i)).toBeInTheDocument();
    expect(screen.queryByTestId('file-chip')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Inspect photo' })).toBeDisabled();
  });

  it('marks a low-confidence result for manual review', async () => {
    createInspection.mockResolvedValue({
      ...DEFECT_RESULT,
      assessment: {
        ...DEFECT_RESULT.assessment,
        confidence: 0.55,
        needsReview: true,
        action: 're_inspect',
      },
    });
    const user = userEvent.setup();
    renderApp();

    await chooseAndInspect(user);

    expect(await screen.findByText(/needs manual review/i)).toBeInTheDocument();
    expect(screen.getByText('Re-inspect')).toBeInTheDocument();
  });
});
