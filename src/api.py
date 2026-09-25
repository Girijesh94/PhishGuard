"""Serve the exact model and URL representation named by its manifest."""
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import json
import logging
import os

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

from features import extract_features, normalize_url, parse_host
from pipeline import ROOT, FEATURES, load_artifact, phishing_scores

logger = logging.getLogger('uvicorn.error')
model, metadata = load_artifact()
feature_ranges = json.loads((ROOT / 'feature_ranges.json').read_text())
LOADED_AT = datetime.now(timezone.utc).isoformat()
LOADED_STAT = (ROOT / 'model.pkl').stat()
RICH_MODEL = metadata.get('model_kind') == 'url_text_structure'


@asynccontextmanager
async def lifespan(app):
    logger.info('Loaded model path=%s sha256=%s variant=%s trained=%s threshold=%s pid=%s',
                ROOT / 'model.pkl', metadata['sha256']['model.pkl'],
                metadata['chosen_variant'], metadata['created_utc'],
                metadata['threshold'], os.getpid())
    yield


app = FastAPI(lifespan=lifespan)


@app.get('/', include_in_schema=False)
def index():
    return RedirectResponse(url='/docs')


class URLRequest(BaseModel):
    url: str = Field(min_length=1, max_length=65536)


def normalize(feature, value):
    lo, hi = feature_ranges[feature]['min'], feature_ranges[feature]['max']
    return max(0.0, min(1.0, (value - lo) / (hi - lo))) if hi != lo else 0.0


@app.get('/health')
def health():
    current = (ROOT / 'model.pkl').stat()
    return {
        'status': 'ok', 'pid': os.getpid(), 'loaded_at': LOADED_AT,
        'model_sha256': metadata['sha256']['model.pkl'],
        'model_variant': metadata['chosen_variant'],
        'trained_at': metadata['created_utc'], 'threshold': metadata['threshold'],
        'restart_required': (current.st_mtime_ns, current.st_size) !=
                            (LOADED_STAT.st_mtime_ns, LOADED_STAT.st_size),
    }


@app.post('/predict')
def predict(req: URLRequest):
    try:
        url = normalize_url(req.url)
        if not parse_host(url):
            raise ValueError('URL must include a hostname')
        raw_features = extract_features(url)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    X = pd.DataFrame({'url': [url]}) if RICH_MODEL else pd.DataFrame([raw_features], columns=FEATURES)
    probability = float(phishing_scores(model, X)[0])
    label = 'phishing' if probability >= metadata['threshold'] else 'legitimate'
    if RICH_MODEL:
        contributions = model.text_contributions(url)
        method = ('Signed TF-IDF times coefficient: text-component log-odds only; '
                  'does not explain the structural component or blended probability.')
    else:
        importances = dict(zip(FEATURES, model.feature_importances_))
        contributions = sorted(
            [{'feature': f, 'value': raw_features[f],
              'contribution': round(normalize(f, raw_features[f]) * importances[f], 4)}
             for f in FEATURES], key=lambda item: item['contribution'], reverse=True)[:3]
        method = 'Normalized value times global importance; not a local explanation.'
    return {
        'url': req.url, 'normalized_url': url, 'label': label,
        'confidence': round(max(probability, 1 - probability), 4),
        'phishing_probability': round(probability, 4),
        'threshold': metadata['threshold'],
        'model_sha256': metadata['sha256']['model.pkl'],
        'score_note': 'Uncalibrated URL model score; legitimate does not certify safety.',
        'top_features': contributions,
        'top_features_method': method,
    }
