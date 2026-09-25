"""Validation-only, bounded comparison on unchanged saved domain splits."""
from datetime import datetime, timezone
from pathlib import Path
import json
import os
import time

import joblib
import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from threadpoolctl import threadpool_limits

from pipeline import DATA, ROOT, REPORTS, assert_disjoint, digest, scores, write_json
from url_model import structural_matrix, text_view, URLClassifier

OUTPUT = ROOT / 'artifacts' / 'richer_model'
CS = [2.0, 8.0]
BLEND_WEIGHTS = [0.25, 0.5, 0.75]


def fit_candidates(splits, baseline_score):
    OUTPUT.mkdir(parents=True, exist_ok=True)
    assert_disjoint(splits)
    plan = {
        'started_utc': datetime.now(timezone.utc).isoformat(),
        'threshold': .5, 'C_values': CS, 'blend_weights': BLEND_WEIGHTS,
        'selection': 'Maximum validation phishing F1 at threshold .5, only if accuracy/precision/recall/F1 improve and FPR decreases versus baseline. Test not used.',
        'text': 'TF-IDF character 3-5 grams, min_df=3, max_features=180000; logistic regression balanced, L2, liblinear.',
        'structure': 'HistGradientBoosting 350 iterations, 31 leaves, learning_rate=.08, min_samples_leaf=30, l2_regularization=10, early_stopping=False.',
        'sha256': {f: digest(ROOT / f) for f in ['data/splits.csv', 'data/urls.csv', 'data/features.csv', 'src/url_model.py', 'src/experiment_richer_model.py']},
        'baseline_validation': baseline_score,
        'test_history': 'The fixed test set has been reported in earlier work. It is reused for comparison, not claimed to be an untouched external benchmark.',
    }
    write_json(OUTPUT / 'plan.json', plan)
    train = splits[splits.split == 'train']
    val = splits[splits.split == 'validation']
    print('Training rows:', len(train), 'Validation rows:', len(val), flush=True)
    print('Test rows remain excluded from model/weight selection.', flush=True)
    results, probabilities = {}, {}

    print('Extracting structural measurements...', flush=True)
    X_train = structural_matrix(train.url)
    X_val = structural_matrix(val.url)
    print('Structural columns:', X_train.shape[1], flush=True)
    structure = HistGradientBoostingClassifier(
        max_iter=350, max_leaf_nodes=31, learning_rate=.08,
        min_samples_leaf=30, l2_regularization=10, early_stopping=False, random_state=42)
    with threadpool_limits(limits=4):
        started = time.monotonic()
        structure.fit(X_train, train.label)
        ps = structure.predict_proba(X_val)[:, 1]
    results['structure'] = scores(val.label, ps)
    probabilities['structure'] = ps
    joblib.dump(structure, OUTPUT / 'structure.pkl')
    print('structure', json.dumps(results['structure']), 'seconds', round(time.monotonic()-started,1), flush=True)
    del X_train, X_val

    print('Fitting character vocabulary on TRAIN rows only...', flush=True)
    vectorizer = TfidfVectorizer(analyzer='char', ngram_range=(3,5), min_df=3,
                                max_features=180000, sublinear_tf=True, lowercase=True,
                                dtype=np.float32)
    X_train = vectorizer.fit_transform([text_view(u) for u in train.url])
    X_val = vectorizer.transform([text_view(u) for u in val.url])
    joblib.dump(vectorizer, OUTPUT / 'vectorizer.pkl')
    print('Text matrix:', X_train.shape, 'nonzeros:', X_train.nnz, flush=True)
    text_models = {}
    for c in CS:
        name = f'char_C{c:g}'
        clf = LogisticRegression(C=c, solver='liblinear', dual=True, class_weight='balanced',
                                 max_iter=500, random_state=42, tol=1e-4)
        started = time.monotonic()
        with threadpool_limits(limits=4):
            clf.fit(X_train, train.label)
            pt = clf.predict_proba(X_val)[:, 1]
        text_models[name] = clf
        results[name] = scores(val.label, pt)
        probabilities[name] = pt
        print(name, json.dumps(results[name]), 'seconds', round(time.monotonic()-started,1),
              'iterations', clf.n_iter_.tolist(), flush=True)
        for weight in BLEND_WEIGHTS:
            key = f'{name}_blend{weight:g}'
            p = weight * pt + (1-weight) * ps
            results[key] = scores(val.label, p)
            probabilities[key] = p
            print(key, json.dumps(results[key]), flush=True)

    eligible = []
    for name, result in results.items():
        if (all(result[m] > baseline_score[m] for m in ['accuracy','precision','recall','f1'])
                and result['false_positive_rate'] < baseline_score['false_positive_rate']):
            eligible.append(name)
    if not eligible:
        write_json(OUTPUT / 'validation.json', {'candidates': results, 'chosen': None})
        raise SystemExit('No candidate improves all target validation metrics; existing model preserved.')
    chosen = max(eligible, key=lambda name: results[name]['f1'])
    if chosen == 'structure':
        selected = URLClassifier(structure_model=structure, text_weight=0.)
    else:
        name = chosen.split('_blend')[0]
        weight = float(chosen.split('_blend')[1]) if '_blend' in chosen else 1.
        selected = URLClassifier(vectorizer, text_models[name],
                                 structure if weight < 1 else None, weight)
    joblib.dump(selected, OUTPUT / 'candidate_model.pkl', compress=3)
    val.assign(phishing_score=probabilities[chosen]).to_csv(OUTPUT / 'validation_predictions.csv', index=False)
    tradeoff = [scores(val.label, probabilities[chosen], t) for t in [.1,.2,.3,.4,.5,.6,.7,.8,.9]]
    write_json(OUTPUT / 'validation.json', {'candidates': results, 'chosen': chosen,
                                          'baseline': baseline_score, 'threshold_tradeoff': tradeoff})
    # Verify serialized inference uses exactly the same preprocessing/components.
    loaded = joblib.load(OUTPUT / 'candidate_model.pkl')
    with threadpool_limits(limits=4):
        check = loaded.predict_proba(val[['url']].iloc[:200])[:, 1]
    np.testing.assert_allclose(check, probabilities[chosen][:200], rtol=1e-6, atol=1e-7)
    print('Chosen:', chosen, 'serialized prediction parity: PASS', flush=True)
    print('Candidate staged; deployed model unchanged.', flush=True)
    return chosen


if __name__ == '__main__':
    from train import main
    main()
