"""Paths, provenance checks and domain-disjoint evaluation helpers."""
from hashlib import file_digest, sha256
from pathlib import Path
import json
import importlib.metadata
import joblib
import numpy as np
from sklearn.metrics import (accuracy_score, average_precision_score, confusion_matrix,
                             f1_score, precision_score, recall_score, roc_auc_score)

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
REPORTS = ROOT / 'artifacts' / 'phase1'
FEATURES = ['url_length', 'special_chars', 'has_ip', 'subdomain_count',
            'entropy', 'digit_ratio', 'path_depth']
THRESHOLD = 0.5


def digest(path):
    with Path(path).open('rb') as stream:
        return file_digest(stream, 'sha256').hexdigest()


def write_json(path, obj):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(obj, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def split_for_domain(domain):
    # Stable with order and additions. Whole shared platforms stay together.
    bucket = int(sha256(('phishguard-domain-v1:42:' + domain).encode()).hexdigest()[:8], 16) % 100
    return 'test' if bucket < 20 else 'validation' if bucket < 40 else 'train'


def assert_disjoint(frame):
    for key in ['domain', 'url']:
        if frame.groupby(key)['split'].nunique().max() != 1:
            raise ValueError(f'{key} occurs in multiple splits')
    for name in ['train', 'validation', 'test']:
        if set(frame.loc[frame.split == name, 'label']) != {0, 1}:
            raise ValueError(f'{name} must contain both labels')


def phishing_scores(model, X):
    return model.predict_proba(X)[:, list(model.classes_).index(1)]


def scores(y, probabilities, threshold=THRESHOLD):
    y = np.asarray(y)
    pred = np.asarray(probabilities) >= threshold
    tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()
    result = {
        'n': len(y), 'benign': int(tn + fp), 'phishing': int(tp + fn),
        'threshold': float(threshold), 'accuracy': float(accuracy_score(y, pred)),
        'precision': float(precision_score(y, pred, zero_division=0)),
        'recall': float(recall_score(y, pred, zero_division=0)),
        'f1': float(f1_score(y, pred, zero_division=0)),
        'false_positive_rate': float(fp / (fp + tn)) if fp + tn else None,
        'confusion_matrix': [[int(tn), int(fp)], [int(fn), int(tp)]],
    }
    if len(set(y)) == 2:
        result.update(roc_auc=float(roc_auc_score(y, probabilities)),
                      average_precision=float(average_precision_score(y, probabilities)))
    return result


def load_artifact(check_data=False):
    metadata = json.loads((ROOT / 'model_metadata.json').read_text(encoding='utf-8'))
    for package, version in metadata.get('versions', {}).items():
        if importlib.metadata.version(package) != version:
            raise ValueError(f'Artifact dependency mismatch: {package}; use the recorded version or retrain')
    names = ['model.pkl', 'src/features.py', 'feature_ranges.json']
    if metadata.get('model_kind') == 'url_text_structure':
        names += ['src/url_model.py']
    if check_data:
        names += ['data/urls.csv', 'data/features.csv', 'data/splits.csv']
    for name in names:
        if digest(ROOT / name) != metadata['sha256'][name]:
            raise ValueError(f'Stale artifact: {name} differs from training manifest; rebuild/retrain')
    model = joblib.load(ROOT / 'model.pkl')
    if list(model.feature_names_in_) != metadata.get('input_columns', FEATURES):
        raise ValueError('Model feature schema differs from application')
    return model, metadata
