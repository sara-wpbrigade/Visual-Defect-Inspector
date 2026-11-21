# Visual Defect Inspector backend

FastAPI service that checks a photo against an operator-chosen category, runs
that category's PatchCore detector, applies the persona rules and stores the
inspection in SQLite.

## Configuration

Each available category lives in `config/categories/<id>.json`. A category is
served only when both its checkpoint and prototype files exist. A JSON file
whose files are not built yet is skipped with a warning, so configuration can
land before training finishes.

`ENABLED_CATEGORIES` optionally limits the served ids (comma separated); leave
it empty to serve every available category. The old single `checkpoint_path`
setting is gone: checkpoints now come from the per-category JSON files.

## Adding a category

1. Train the anomaly model on the category's normal images:

   ```bash
   uv run python -m scripts.train_anomaly <category>
   ```

2. Build the embedding prototype used by the yes/no category gate:

   ```bash
   uv run python -m scripts.build_prototypes <category> [--limit N]
   ```

   This embeds `data/mvtec/<category>/train/good` with the same encoder used at
   request time and writes the `prototype_path` named in the config.

3. Calibrate the gate cutoff:

   ```bash
   uv run python -m scripts.calibrate_category_gate
   ```

   The script reports each available category's own-category minimum, first
   percentile and median similarity, the highest similarity to other
   categories and to `data/out_of_scope/`, and a suggested `min_similarity`.
   It only prints; update the JSON file yourself.

4. Create or update `config/categories/<id>.json` with:

   - `id` matching the file name (`^[a-z][a-z0-9_]{0,40}$`)
   - `display_name` and `description`
   - `checkpoint_path` and `prototype_path`, relative to `backend/`
   - `min_similarity` between 0 and 1
   - a non-empty `defect_types` list
   - `severity_bands` with `0 < low_max < medium_max < 1`

5. Restart the service. `GET /categories` now lists the category, and
   `POST /inspections` accepts its id as the required `category` field.

## Optional voice note

`POST /inspections` also accepts an optional multipart field `voice_note`. The
audio container is read from the bytes (WAV, MP3, OGG, WebM or M4A), capped at
5 MB and 60 seconds. A local faster-whisper model transcribes it on CPU
(`int8`), the text is cleaned and length-capped, and only the transcript is
stored with the inspection; the audio itself is never saved.

- Silent or speechless audio returns `voice_note.status = "no_speech"` and never
  loads the model.
- A transcribed note is passed to the report writer and is included in the PDF.
- The first voice request downloads the model (`base`, about 145 MB). Override
  it with `WHISPER_MODEL`, `WHISPER_DEVICE` and `WHISPER_COMPUTE_TYPE`; in Docker
  the cache lives under the mounted data folder via `HF_HOME`.
- Invalid audio is `400`, over the byte or duration limit is `413`, and a speech
  model failure is `503`.

## Checks

From `backend/`:

```bash
uv run ruff format .
uv run ruff check .
uv run pyright
uv run pytest
```
