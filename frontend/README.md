# Visual Defect Inspector: frontend slice

The React + Vite UI for the part of the pipeline that exists today: **photo in, QC facts and the
AI-written report out**. It calls `POST /inspections`, shows loading, success and error states, and
renders the verdict, confidence, severity, flagged area, anomaly score, recommended action and the
report: summary, findings, recommendations, the AI-estimated defect type, the flagged region and
any manual-review or voice-note-conflict notice.

Not in this slice yet: defect overlay image, inspection history, voice note capture, PDF
downloads, batch view and CSV export. Those arrive with backend Steps 7 to 11.

## Stack and layout

- React 19 + Vite 8, plain JavaScript (the SOW names `services/api.js`)
- Vitest + React Testing Library + jsdom for tests
- ESLint (flat config) + Prettier for quality gates
- One backend module: `src/services/api.js`. Components never call `fetch` themselves.

```
frontend/
├── .env.example          VITE_API_BASE_URL (empty = use the dev proxy)
├── eslint.config.js
├── vite.config.js        dev proxy + Vitest config
├── src/
│   ├── main.jsx
│   ├── App.jsx           upload panel + result column
│   ├── constants.js      labels, limits, status copy
│   ├── services/api.js   the only HTTP client
│   ├── hooks/            useInspection state machine
│   ├── components/       UploadPanel, ResultCard, StatusPanels
│   ├── lib/              formatting and client-side image validation
│   └── test/setup.js
└── README.md
```

## Run locally

Use two terminals. The backend must be running because the UI calls the real API.

**Terminal 1, from `backend/`:**

```
uv run uvicorn app.main:app --reload
```

Wait for the first request to load the PatchCore checkpoint (about 5 to 10 seconds; later
inspections are fast). The first request also needs `backend/.env` with `GEMINI_API_KEY` and
`GEMINI_MODEL`, because the settings module validates them at startup.

**Terminal 2, from `frontend/`:**

```
npm install
npm run dev
```

Open <http://localhost:5173>. Choose a photo from
`backend/data/mvtec/bottle/test/` or drop one into the panel.

Expected on `broken_large/000.png`: **Defect / High / Reject**, confidence about 93.7%, flagged
area about 17.5%, anomaly score about 0.937.

The Vite dev server proxies `/inspections` and `/health` to `http://127.0.0.1:8000`, so the browser
uses one origin and the backend needs no CORS setup. Point it elsewhere with:

```
BACKEND_URL=http://127.0.0.1:9000 npm run dev
```

## API contract used by the UI

`POST /inspections` with multipart field `image` returns `201`:

```json
{
  "inspection_id": "a390399a0ce54f6683c9231df1fdd839",
  "score": 0.936946451663971,
  "assessment": {
    "verdict": "defect",
    "confidence": 0.936946451663971,
    "needs_review": false,
    "severity": "high",
    "area_ratio": 0.1750030517578125,
    "action": "reject",
    "location": { "region": "lower center", "bbox": [0.348, 0.305, 0.895, 0.93] }
  },
  "report": {
    "report_id": "a390399a0ce54f6683c9231df1fdd839",
    "generated_at": "2026-11-18T08:07:19.671664Z",
    "persona": "factory_qc_operator",
    "source": "ai",
    "manual_review_notice": null,
    "content": {
      "summary": "A high severity defect covers the lower center of the item.",
      "findings": ["The flagged area covers 17.5% of the item."],
      "recommendations": ["Reject the item and keep it out of the batch."],
      "defect_type": "contamination",
      "voice_note_conflict": null
    }
  }
}
```

`api.js` converts this to camelCase (`inspectionId`, `areaRatio`, `needsReview`, `location.region`,
`reportId`, `generatedAt`, `source`, `manualReviewNotice`, `content.defectType`,
`content.voiceNoteConflict`) and checks the shape, so a broken contract becomes a visible error
instead of a blank card. `location` is `null` for a pass, `source` is `ai` or `template`, and
`manual_review_notice` and `voice_note_conflict` are `null` unless they apply. Errors map to
operator copy:

| Status          | UI message                                                     |
| --------------- | -------------------------------------------------------------- |
| network failure | Could not reach the server. Check that the backend is running. |
| 400             | Not a readable JPEG/PNG.                                       |
| 413             | Photo is too large (10 MB limit).                              |
| 422             | The photo was not sent correctly.                              |
| 503             | The inspection model is unavailable.                           |
| other           | The server's `detail`, otherwise a generic message.            |

Client-side checks (JPEG/PNG type, non-empty, 10 MB) only save a pointless upload. The backend
still validates the real bytes, dimensions and content.

## Quality gates

Run from `frontend/`, in this order:

```
npm run format
npm run lint
npm run format:check
npm run test
npm run test:coverage
npm run build
```

Current result: **61 tests pass, 100% statements/functions/lines, 96% branches** (threshold 85%).
Coverage HTML is written to `frontend/coverage/`.

## Testing approach

- `src/services/api.test.js` covers the HTTP contract: multipart field, 201 body, the report and
  location mapping, 400/413/422/503, network failure, non-JSON error bodies and malformed success
  bodies (missing or invalid report, empty lists, unknown source, out-of-range location).
- `src/hooks/useInspection.test.jsx` covers the idle → loading → success/error state machine.
- `UploadPanel.test.jsx` covers valid/invalid/empty/oversized files, drag-and-drop, camera button,
  busy state and preview URL cleanup.
- `ResultCard.test.jsx` covers the facts, the report section (summary, findings, recommendations,
  AI/template badge, defect type chip and flagged region), the manual-review banner, the hidden or
  not-determined defect type and the voice-note-conflict notice.
- `App.test.jsx` is the integration test of the frontend flow with a mocked API: upload, loading,
  verdict with the report, low-confidence review warning, error and reset.

The API is mocked in unit tests so they stay deterministic; the real model is exercised by the
backend tests, by the manual flow above, and by the curl checks in the handoff.

## Troubleshooting

| Symptom                                  | Cause                                                                       |
| ---------------------------------------- | --------------------------------------------------------------------------- |
| "Could not reach the server"             | Backend is not running on port 8000, or `BACKEND_URL` is wrong.             |
| First inspection takes seconds           | The checkpoint loads on the first request.                                  |
| 503 after an image upload                | The detector failed or the checkpoint path is wrong; check the backend log. |
| 400 on a valid-looking photo             | The backend reads the real file bytes, not the filename. Use a JPEG/PNG.    |
| `npm run test:coverage` fails thresholds | Add tests, do not lower the threshold without a reason.                     |
