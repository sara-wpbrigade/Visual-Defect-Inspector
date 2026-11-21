# Trained models

The detector is a real, locally trained **PatchCore** model. The checkpoints are
large binary files, so they are **not in the normal Git history**. A fresh clone
must get them in one of the ways below; otherwise `/categories` is empty and the
inspection endpoint cannot run.

## What is required

Only the configured checkpoints and prototypes matter:

| Category   | Checkpoint used by `config/categories/*.json`                                 | Size        |
| ---------- | ----------------------------------------------------------------------------- | ----------- |
| Bottle     | `backend/results/Patchcore/MVTecAD/bottle/v1/weights/lightning/model.ckpt`    | ~108 MB     |
| Metal nut  | `backend/results/Patchcore/MVTecAD/metal_nut/v0/weights/lightning/model.ckpt` | ~108 MB     |
| Screw      | `backend/results/Patchcore/MVTecAD/screw/v0/weights/lightning/model.ckpt`     | ~114 MB     |
| Prototypes | `backend/results/prototypes/{bottle,metal_nut,screw}.npz`                     | ~20 KB each |

`bottle` is enough for the default sample flow. The loader logs a warning and
skips any category whose checkpoint or prototype is missing.

## Option A — run on the machine where the models were trained

If you already have `backend/results/` locally, nothing else is needed. This is
the current demo machine.

## Option B — Git LFS (recommended if the repo must stay self-contained)

GitHub rejects individual files over 100 MB in normal Git. Git LFS handles the
three checkpoints and the tiny prototypes.

```bash
# One-time setup
git lfs install
git lfs track "backend/results/Patchcore/**/*.ckpt"
git lfs track "backend/results/prototypes/*.npz"

# The .gitattributes file in this repo already contains these patterns.
git add .gitattributes

# Force-add only the configured files; results/ is git-ignored by default.
git add -f backend/results/Patchcore/MVTecAD/bottle/v1/weights/lightning/model.ckpt
git add -f backend/results/Patchcore/MVTecAD/metal_nut/v0/weights/lightning/model.ckpt
git add -f backend/results/Patchcore/MVTecAD/screw/v0/weights/lightning/model.ckpt
git add -f backend/results/prototypes/*.npz

git commit -m "Add trained PatchCore checkpoints via Git LFS"
git lfs push --all origin main
git push origin main
```

On another machine:

```bash
git lfs install
git clone <repo-url>
cd defect-inspector
git lfs pull
```

The approximate LFS payload is 330 MB, within GitHub's free 1 GB quota.

## Option C — GitHub Release (full bundle, recommended for the deliverable)

This is the option that satisfies the “fresh clone runs within 10 minutes”
requirement while keeping **all three categories** (bottle, metal nut, screw).

From `backend/results`:

```bash
zip -r ~/Downloads/defect-inspector-models.zip \
  Patchcore/MVTecAD/bottle/v1/weights/lightning/model.ckpt \
  Patchcore/MVTecAD/metal_nut/v0/weights/lightning/model.ckpt \
  Patchcore/MVTecAD/screw/v0/weights/lightning/model.ckpt \
  prototypes/bottle.npz \
  prototypes/metal_nut.npz \
  prototypes/screw.npz
```

This produces a **~301 MB zip** (about 330 MB unpacked). Do not zip the whole
`vN` folder: it also contains prediction images, which are not needed.

Then:

1. Push the repo to GitHub.
2. Open **Releases → Draft a new release**.
3. Create tag `v1.0.0`, title it “Models”, and attach
   `defect-inspector-models.zip`.
4. Publish the release.

On the target machine:

```bash
git clone <repo-url>
cd defect-inspector
unzip ~/Downloads/defect-inspector-models.zip -d backend/results
cp backend/.env.example backend/.env
# edit .env: GEMINI key, or REPORT_WRITER=template
docker compose up --build
open http://localhost:5173
```

The category catalog then returns all three categories. The first Docker build
dominates the 10-minute budget; the 301 MB download is fast on a normal
connection. The optional first voice request downloads the Whisper model
(~404 MB), so leave the voice-note test out of the 10-minute first-run budget.

## Bottle-only fallback (smaller upload)

If you only need a quick 5-minute upload, ship **only bottle** (~108 MB):

```bash
zip -r ~/defect-bottle-model.zip \
  Patchcore/MVTecAD/bottle/v1/weights/lightning/model.ckpt \
  prototypes/bottle.npz
```

Unzip it into `backend/results` on the target. The app will serve **bottle
only**; the loader logs a warning and skips the other two categories.

## Option D — train again

This needs the MVTec AD images under `backend/data/mvtec/<category>`.

```bash
cd backend
uv run python -m scripts.train_anomaly bottle
uv run python -m scripts.build_prototypes bottle
uv run python -m scripts.calibrate_category_gate
```

Repeat for `metal_nut` and `screw` if you want all three categories. Training
with the 1% coreset takes about 2 minutes per category on the M1 Air; the
default 10% coreset took roughly 22 minutes.

## Docker note

Compose mounts `./backend/results` read-only into `/app/results`. The files must
exist on the host **before** `docker compose up --build`, otherwise the backend
starts with no available categories.
