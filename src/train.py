"""Train richer URL models, selecting only on domain-disjoint validation."""
from datetime import datetime, timezone
import importlib.metadata
import json
import os
import shutil

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

from compute_feature_ranges import compute_ranges
from experiment_richer_model import fit_candidates, OUTPUT
from pipeline import (DATA, ROOT, REPORTS, FEATURES, THRESHOLD, assert_disjoint,
                      digest, phishing_scores, scores, split_for_domain, write_json)


def main():
    manifest = json.loads((REPORTS / 'features_manifest.json').read_text())
    for key, path in [('urls_sha256', DATA / 'urls.csv'),
                      ('features_sha256', DATA / 'features.csv'),
                      ('extractor_sha256', ROOT / 'src/features.py')]:
        if manifest[key] != digest(path):
            raise ValueError(f'Stale feature build: {path}; run build_features.py')
    df = pd.read_csv(DATA / 'features.csv')
    df['split'] = df.domain.map(split_for_domain)
    assert_disjoint(df)
    metadata_cols = ['url', 'raw_url', 'label', 'source', 'domain', 'split']
    splits = df[metadata_cols]
    splits.to_csv(DATA / 'splits.csv', index=False)
    print('=== unchanged registered-domain split policy ===', flush=True)
    print(pd.crosstab(df.split, df.label), flush=True)
    train = df[df.split == 'train']
    validation = df[df.split == 'validation']
    test = df[df.split == 'test']
    OUTPUT.mkdir(parents=True, exist_ok=True)

    # Fixed seven-feature reference for a controlled comparison. No canaries.
    print('Fitting fixed seven-feature reference...', flush=True)
    baseline = RandomForestClassifier(n_estimators=200, random_state=42,
                                     min_samples_leaf=3, class_weight='balanced_subsample',
                                     n_jobs=min(4, os.cpu_count() or 1))
    baseline.fit(train[FEATURES], train.label)
    baseline_metrics = scores(validation.label, phishing_scores(baseline, validation[FEATURES]))
    joblib.dump(baseline, OUTPUT / 'baseline_model.pkl')
    write_json(OUTPUT / 'baseline_validation.json', baseline_metrics)
    print('Reference validation:', json.dumps(baseline_metrics), flush=True)
    del baseline

    chosen = fit_candidates(splits, baseline_metrics)
    model = joblib.load(OUTPUT / 'candidate_model.pkl')
    validation_report = json.loads((OUTPUT / 'validation.json').read_text())
    frozen = {
        'chosen': chosen, 'candidate_sha256': digest(OUTPUT / 'candidate_model.pkl'),
        'threshold': THRESHOLD, 'selection_dataset': 'validation only',
        'test_history': 'Previously reported internal holdout; not a fresh external benchmark.',
    }
    write_json(OUTPUT / 'frozen_selection.json', frozen)

    # No fit on validation or test. Copy the exact selected train-only artifact.
    temporary = ROOT / 'model.pkl.tmp'
    shutil.copyfile(OUTPUT / 'candidate_model.pkl', temporary)
    os.replace(temporary, ROOT / 'model.pkl')
    write_json(ROOT / 'feature_ranges.json', compute_ranges(df))
    test[['url']].to_csv(DATA / 'X_test.csv', index=False)
    test[['label']].to_csv(DATA / 'y_test.csv', index=False)
    write_json(REPORTS / 'validation.json', validation_report)
    shutil.copyfile(OUTPUT / 'validation_predictions.csv', REPORTS / 'validation_predictions.csv')
    metadata = {
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'model_kind': 'url_text_structure',
        'chosen_variant': chosen, 'threshold': THRESHOLD, 'input_columns': ['url'],
        'feature_names': ['url'], 'text_weight': model.text_weight,
        'text_ngrams': [3,5], 'vocabulary_size': len(model.vectorizer.vocabulary_) if model.vectorizer else 0,
        'structural_feature_count': int(model.structure_model.n_features_in_) if model.structure_model else 0,
        'selection': 'Maximum validation phishing F1 at .5 among predefined candidates improving all accuracy/precision/recall/F1 and FPR versus the seven-feature reference. No test selection.',
        'split': 'Unchanged SHA256 registered-domain hash, seed 42: 60/20/20 by domain, whole shared platforms grouped.',
        'split_counts': {name: df[df.split == name].label.value_counts().sort_index().to_dict()
                         for name in ['train','validation','test']},
        'versions': {name: importlib.metadata.version(name)
                     for name in ['pandas','scikit-learn','numpy','scipy','joblib','tldextract']},
        'sha256': {name: digest(ROOT / name) for name in [
            'model.pkl','feature_ranges.json','data/urls.csv','data/features.csv','data/splits.csv',
            'src/features.py','src/url_model.py','src/train.py','src/experiment_richer_model.py',
            'src/build_final_dataset.py','src/build_features.py']},
        'baseline_model_sha256': digest(OUTPUT / 'baseline_model.pkl'),
        'intended_use': 'Research URL screening; no domain reputation or page inspection; scores uncalibrated.',
    }
    write_json(ROOT / 'model_metadata.json', metadata)
    print('Published validation-selected model:', chosen, flush=True)
    print('Threshold:', THRESHOLD, 'Model SHA256:', metadata['sha256']['model.pkl'], flush=True)


if __name__ == '__main__':
    main()
