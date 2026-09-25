# PhishGuard

Offline phishing-URL screening using URL character patterns and structural measurements.

The selected model averages character TF-IDF/logistic-regression and structural
histogram-gradient-boosting scores. Model/weight selection uses registered-domain
validation data. The operating threshold remains **0.5**.

On the same 70,494 test URLs, accuracy improved from **70.90% to 88.24%** and phishing
F1 from **70.55% to 87.58%**. Precision is **86.71%**, recall **88.47%**, and benign
false-positive rate **11.96%**. These are internal benchmark results; a legitimate
prediction does not establish safety. See [metrics.md](metrics.md) for the complete
comparison, uncertainty intervals, source-specific regressions, and limitations.

## Reproduce

Use Python 3.12 and the package versions in `model_metadata.json`.
Install dependencies with `python -m pip install -r requirements.txt`.
Input snapshots: `data/malicious_phish.csv`, `data/verified_online.csv`,
and `data/tranco_38KVL.csv`.

```text
python src/build_final_dataset.py
python src/build_features.py
python src/train.py
python src/evaluate.py
python -m unittest discover -s src -p "test_*.py"
```

All scripts resolve paths relative to the repository. The `src` modules must be
on the Python import path when loading the custom model directly; the supplied
entry scripts and API command already handle this.

Training fits the fixed seven-feature reference plus the predefined richer
candidates. It selects validation F1 at 0.5 among candidates improving every
aggregate validation metric over the reference, and saves the selected
training-only model. TF-IDF vocabulary and IDF weights never see validation/test.
The inference input is now a single `url` column, not seven precomputed counts.

Registered domains, including whole shared hosting platforms, cannot cross the
train/validation/test splits. The comparison retains the same dataset, labels,
domain assignments and threshold. The test corpus was inspected in earlier
development; it is not a fresh external evaluation.

## Local API

```text
python -m uvicorn api:app --app-dir src --reload --reload-dir src --port 8000
```

`GET /health` reports the loaded model hash, variant, training time, PID and whether
the model file changed after loading. Restart after retraining; source reload
does not watch the model file. Startup rejects mismatched model, feature code,
ranges or recorded dependency versions.

`POST /predict` accepts `{"url":"https://www.google.com"}`.
The response retains `label`, `confidence`, and `top_features`. Confidence is an
uncalibrated model score. For the richer model, top features are signed character
n-gram log-odds contributions from the text component only; they do not explain
the structural component or blended probability. The service does not visit URLs.

## Evidence and remaining limits

- `metrics.md`: full before/after report, validation tradeoff and test slices.
- `model_metadata.json`: artifact hashes, library versions and selected settings.
- `data/splits.csv`: unchanged raw/canonical URLs, labels, sources, domains and splits.
- `artifacts/richer_model/plan.json` and `validation.json`: bounded candidate protocol.
- `artifacts/richer_model/baseline_model.pkl`: seven-feature reference on the same training rows.
- `artifacts/phase1/evaluation.json`: complete results and paired domain-bootstrap intervals.
- `artifacts/phase1/test_predictions.csv` and `test_errors.csv`: every test outcome.
- `artifacts/before_richer_model/`: preserved prior model, data, source and reports.

The inherited keyword quarantine excludes 22,751 uncertain benign labels and may
bias text features around account/login pages. Kaggle labels remain unadjudicated,
Tranco popularity is a benign proxy, and PhishTank status is historical. The
overall improvement includes a regression on Tranco homepages: FPR rose from
10.74% to 18.39%. No domain reputation, content or redirect inspection is performed.
A recent, independently adjudicated external evaluation is still needed before
treating this as a dependable security decision.

## Further validation experiment

Three learned combiners were tested using predictions from training-domain-disjoint
folds. None passed all predeclared validation guards, so the deployed model was
retained. See [the stacking report](artifacts/stacking/report.md) for the tradeoff.

## Express API and mobile client

Run the model service first:

```text
python -m uvicorn api:app --app-dir src --reload --reload-dir src --port 8000
```

Create a PostgreSQL database, copy `backend/.env.example` to `backend/.env`, set
`DATABASE_URL` and a random `JWT_SECRET` of at least 32 bytes, then:

```text
cd backend
npm ci
npm run migrate
npm start
```

The Express routes are `POST /api/auth/register`, `POST /api/auth/login`,
`GET /api/me`, `POST /api/scans` (body `{"url":"https://example.com"}`) and
`GET /api/scans?limit=50`. All scan routes require
`Authorization: Bearer <token>`. The scan route forwards the URL to FastAPI,
stores the result under the authenticated user, and returns that result. The
backend does not open the submitted URL. `GET /health` checks database access.

For the Expo client, set `EXPO_PUBLIC_API_URL` to the Express server's reachable
address (for a physical phone, use the computer's LAN IP, not localhost):

```text
cd mobile
npm ci
npx expo start
```

The client keeps JWTs in Expo SecureStore, offers URL entry and QR scanning, and
shows recent scans. A QR code only fills the input; the user submits it to
analyze. Android and iOS are the intended platforms. For a device over the
network, configure backend origin, firewall and TLS appropriately. The model
confidence is uncalibrated and a legitimate result does not prove safety.
