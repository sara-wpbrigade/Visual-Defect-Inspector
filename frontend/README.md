# Visual Defect Inspector frontend

React 19 + Vite 8 UI for the factory QC workflow. The root
[`README.md`](../README.md) and [`docs/PROJECT_GUIDE.md`](../docs/PROJECT_GUIDE.md)
are the source of truth for setup and architecture.

## What it contains

- **Inspection tab**: photo/camera/drag-drop, category, batch ID, optional voice
  note, decision-first result, annotated overlay, confidence/facts, AI report,
  transcript, PDF download.
- **Batches & History tab**: KPI dashboard, batch table with inline detail,
  history filters, pagination, CSV export and PDF downloads.
- Dark/light theme, keyboard shortcuts, toasts, error boundary and accessible
  loading/empty/error states.
- All HTTP calls go through one module: `src/services/api.js`.

## Run

From the repo root:

```bash
cd backend
uv run uvicorn app.main:app --reload

# second terminal
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>. Vite proxies `/inspections`, `/batches`,
`/categories` and `/health` to `http://127.0.0.1:8000`; override with
`BACKEND_URL=http://127.0.0.1:9000 npm run dev`.

For the full Docker stack, use `docker compose up --build` from the repo root
and open <http://localhost:5173>.

## Quality gates

```bash
npm run format:check
npm run lint
npm run test
npm run test:coverage
npm run build
```

Current result: **148 tests**, **93.8% statements / 85.7% branches**,
ESLint/Prettier clean.
