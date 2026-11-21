import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { downloadPdfReport } from '../services/api';
import { ResultCard } from './ResultCard';

vi.mock('../services/api', () => ({ downloadPdfReport: vi.fn() }));

beforeEach(() => {
  downloadPdfReport.mockReset();
});

const BASE_CONTENT = {
  summary: 'A high severity defect covers the lower center of the item.',
  findings: [
    'The flagged area covers 17.5% of the item.',
    'The defect sits in the lower center region.',
  ],
  recommendations: ['Quarantine the batch and check the line before the next run.'],
  defectType: 'contamination',
  voiceNoteConflict: null,
};

/** Build a report with one field of the content overridden. */
function makeReport({ content = {}, ...overrides } = {}) {
  return {
    reportId: 'defect001',
    generatedAt: '2026-11-18T08:07:19.671664Z',
    persona: 'factory_qc_operator',
    source: 'ai',
    manualReviewNotice: null,
    ...overrides,
    content: { ...BASE_CONTENT, ...content },
  };
}

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
    location: null,
  },
  report: makeReport({ reportId: 'pass001', content: { defectType: null } }),
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
    location: { region: 'lower center', bbox: [0.348, 0.305, 0.895, 0.93] },
  },
  report: makeReport(),
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
    location: { region: 'upper left', bbox: [0.05, 0.05, 0.4, 0.4] },
  },
  report: makeReport({
    reportId: 'review001',
    manualReviewNotice:
      'This result is close to the decision cutoff. A second operator should review it.',
  }),
};

describe('ResultCard', () => {
  it('shows a pass with its confidence, severity and recommended action', () => {
    render(<ResultCard result={PASS_RESULT} onReset={vi.fn()} />);

    expect(screen.getAllByText('Pass').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Accept').length).toBeGreaterThan(0);
    expect(screen.getByText('78.2%')).toBeInTheDocument();
    expect(screen.getByText('None')).toBeInTheDocument();
    expect(screen.getByText('0.218')).toBeInTheDocument();
    expect(screen.getByText('pass001')).toBeInTheDocument();
    expect(screen.queryByText(/needs manual review/i)).not.toBeInTheDocument();
  });

  it('shows a high severity defect as a reject', () => {
    render(<ResultCard result={REJECT_RESULT} onReset={vi.fn()} />);

    expect(screen.getAllByText('Defect').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Reject').length).toBeGreaterThan(0);
    expect(screen.getByText('High')).toBeInTheDocument();
    expect(screen.getByText('17.5%')).toBeInTheDocument();
    expect(screen.getByText('93.7%')).toBeInTheDocument();
  });

  it('flags a borderline score as needing manual review', () => {
    render(<ResultCard result={REVIEW_RESULT} onReset={vi.fn()} />);

    expect(screen.getAllByText(/needs manual review/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText('Re-inspect').length).toBeGreaterThan(0);
  });

  it('renders the AI report under the facts', () => {
    render(<ResultCard result={REJECT_RESULT} onReset={vi.fn()} />);

    expect(screen.getByText('Report')).toBeInTheDocument();
    expect(screen.getByText('AI-written')).toBeInTheDocument();
    expect(screen.getByText(BASE_CONTENT.summary)).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Findings' })).toBeInTheDocument();
    expect(screen.getByText(BASE_CONTENT.findings[0])).toBeInTheDocument();
    expect(screen.getByText(BASE_CONTENT.findings[1])).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Recommendations' })).toBeInTheDocument();
    expect(screen.getByText(BASE_CONTENT.recommendations[0])).toBeInTheDocument();
    expect(screen.getByText('Defect type: contamination')).toBeInTheDocument();
    expect(screen.getByText('estimated by AI')).toBeInTheDocument();
    expect(screen.getByText('Flagged area: lower center')).toBeInTheDocument();
  });

  it('shows the report manual review notice as a warning banner', () => {
    render(<ResultCard result={REVIEW_RESULT} onReset={vi.fn()} />);

    const banner = screen.getByRole('alert');

    expect(banner).toHaveTextContent('Manual review required.');
    expect(banner).toHaveTextContent('A second operator should review it.');
  });

  it('hides the defect type chip for a pass without a type', () => {
    render(<ResultCard result={PASS_RESULT} onReset={vi.fn()} />);

    expect(screen.queryByText(/defect type/i)).not.toBeInTheDocument();
    expect(screen.queryByText('Flagged area:')).not.toBeInTheDocument();
  });

  it('says the defect type is not determined when a defect has none', () => {
    render(
      <ResultCard
        result={{ ...REJECT_RESULT, report: makeReport({ content: { defectType: null } }) }}
        onReset={vi.fn()}
      />,
    );

    expect(screen.getByText('Defect type: not determined')).toBeInTheDocument();
    expect(screen.queryByText('estimated by AI')).not.toBeInTheDocument();
  });

  it('labels a template report as offline', () => {
    render(
      <ResultCard
        result={{
          ...PASS_RESULT,
          report: makeReport({ source: 'template', content: { defectType: null } }),
        }}
        onReset={vi.fn()}
      />,
    );

    expect(screen.getByText('Template (offline)')).toBeInTheDocument();
    expect(screen.queryByText('AI-written')).not.toBeInTheDocument();
  });

  it('shows a voice note conflict only when the report flags one', () => {
    const conflict = 'The voice note says upper left, but the flagged area is lower center.';
    render(
      <ResultCard
        result={{
          ...REJECT_RESULT,
          report: makeReport({ content: { voiceNoteConflict: conflict } }),
        }}
        onReset={vi.fn()}
      />,
    );

    expect(screen.getByText(/voice note conflict/i)).toBeInTheDocument();
    expect(screen.getByText(conflict)).toBeInTheDocument();
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

    expect(screen.getAllByText('unknown').length).toBeGreaterThan(0);
    expect(screen.getAllByText('critical').length).toBeGreaterThan(0);
    expect(screen.getAllByText('escalate').length).toBeGreaterThan(0);
    expect(screen.getByText(/standard procedure/i)).toBeInTheDocument();
  });

  it('offers a fresh inspection and forwards the reset', async () => {
    const user = userEvent.setup();
    const onReset = vi.fn();
    render(<ResultCard result={PASS_RESULT} onReset={onReset} />);

    await user.click(screen.getByRole('button', { name: 'Inspect another photo' }));

    expect(onReset).toHaveBeenCalledOnce();
  });

  it('switches between the overlay and the original photo', async () => {
    const user = userEvent.setup();
    render(
      <ResultCard
        result={{
          ...REJECT_RESULT,
          images: {
            photo: '/inspections/defect001/photo',
            overlay: '/inspections/defect001/overlay',
            thumbnail: '/inspections/defect001/thumbnail',
          },
        }}
        onReset={vi.fn()}
      />,
    );

    expect(screen.getByAltText('Anomaly overlay mask')).toHaveAttribute(
      'src',
      '/inspections/defect001/overlay',
    );

    await user.click(screen.getByRole('button', { name: 'Original Photo' }));
    expect(screen.getByAltText('Original inspected photo')).toHaveAttribute(
      'src',
      '/inspections/defect001/photo',
    );
  });

  it('downloads the PDF report and shows a failure', async () => {
    const user = userEvent.setup();
    downloadPdfReport.mockResolvedValueOnce();
    render(
      <ResultCard
        result={{ ...REJECT_RESULT, reportPdfAvailable: true, reportPdfUrl: '/report.pdf' }}
        onReset={vi.fn()}
      />,
    );

    await user.click(screen.getByRole('button', { name: 'Download PDF Report' }));
    expect(downloadPdfReport).toHaveBeenCalledWith('defect001');

    downloadPdfReport.mockRejectedValueOnce(new Error('No report'));
    await user.click(screen.getByRole('button', { name: 'Download PDF Report' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('No report');
  });

  it('disables the PDF button when no report is available', () => {
    render(<ResultCard result={PASS_RESULT} onReset={vi.fn()} />);

    expect(screen.getByRole('button', { name: 'Download PDF Report' })).toBeDisabled();
  });

  it('shows a transcribed voice note', () => {
    render(
      <ResultCard
        result={{
          ...REJECT_RESULT,
          voiceNote: {
            status: 'transcribed',
            text: 'The cap is chipped.',
            language: 'en',
            durationSeconds: 4,
            truncated: false,
          },
        }}
        onReset={vi.fn()}
      />,
    );

    expect(screen.getByText(/the cap is chipped/i)).toBeInTheDocument();
    expect(screen.getByText('Lang: en')).toBeInTheDocument();
    expect(screen.getByText('Duration: 4s')).toBeInTheDocument();
  });

  it('shows the batch decision, category and batch id when present', () => {
    render(
      <ResultCard
        result={{
          ...REJECT_RESULT,
          batchDecision: 'Rejected',
          batchId: 'batch-1',
          category: 'bottle',
        }}
        onReset={vi.fn()}
      />,
    );

    expect(screen.getAllByText(/Reject/).length).toBeGreaterThan(0);
    expect(screen.getByText('bottle')).toBeInTheDocument();
    expect(screen.getByText('batch-1')).toBeInTheDocument();
  });
});
