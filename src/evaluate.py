"""Evaluate the frozen richer model against the seven-feature reference."""
import json
import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import classification_report
from threadpoolctl import threadpool_limits

from features import extract_features, normalize_url
from pipeline import (DATA, ROOT, REPORTS, FEATURES, assert_disjoint, digest,
                      load_artifact, phishing_scores, scores, write_json)

DIAGNOSTIC_URLS = [
    'http://google.com', 'https://www.google.com',
    'http://secure-paypal-login.verify-account.tk/update/account.php?id=12345',
    'http://192.168.1.1/admin/login',
]
METRICS = ['accuracy', 'precision', 'recall', 'f1', 'false_positive_rate']


def metric_vector(counts):
    tn, fp, fn, tp = counts
    return np.array([(tn+tp)/max(tn+fp+fn+tp,1), tp/max(tp+fp,1),
                     tp/max(tp+fn,1), 2*tp/max(2*tp+fp+fn,1), fp/max(tn+fp,1)])


def cluster_intervals(test, probabilities, reference, repeats=300):
    y = test.label.to_numpy()
    grouped = pd.DataFrame({'domain': test.domain.to_numpy()})
    for name, p in [('new', probabilities), ('old', reference)]:
        pred = p >= .5
        for column, values in [('tn',(y==0)&~pred), ('fp',(y==0)&pred),
                               ('fn',(y==1)&~pred), ('tp',(y==1)&pred)]:
            grouped[name+'_'+column] = values
    counts = grouped.groupby('domain').sum().to_numpy(dtype=float)
    rng = np.random.default_rng(42)
    samples, deltas = [], []
    for _ in range(repeats):
        total = counts[rng.integers(0,len(counts),len(counts))].sum(axis=0)
        current, previous = metric_vector(total[:4]), metric_vector(total[4:])
        samples.append(current)
        deltas.append(current-previous)
    def bounds(values):
        return {name: np.quantile(np.asarray(values)[:,i],[.025,.975]).tolist()
                for i,name in enumerate(METRICS)}
    return bounds(samples), bounds(deltas)


def main():
    model, metadata = load_artifact(check_data=True)
    if metadata.get('model_kind') != 'url_text_structure':
        raise ValueError('Run the current train.py before evaluating the richer model')
    df = pd.read_csv(DATA / 'features.csv')
    splits = pd.read_csv(DATA / 'splits.csv')
    assert_disjoint(splits)
    if not df.url.equals(splits.url):
        raise ValueError('Feature rows and split manifest do not match')
    test = df[splits.split == 'test'].copy()
    if not test.raw_url.map(normalize_url).equals(test.url):
        raise ValueError('Raw and canonical URL representations differ')
    reference_path = ROOT / 'artifacts/richer_model/baseline_model.pkl'
    if digest(reference_path) != metadata['baseline_model_sha256']:
        raise ValueError('Reference model differs from training manifest')
    reference = joblib.load(reference_path)
    with threadpool_limits(limits=4):
        p = phishing_scores(model, test[['url']])
        raw_p = phishing_scores(model, test[['raw_url']].rename(columns={'raw_url':'url'}))
        old_p = phishing_scores(reference, test[FEATURES])
    np.testing.assert_allclose(raw_p, p, rtol=1e-12, atol=1e-12)
    del reference
    overall, baseline = scores(test.label,p), scores(test.label,old_p)
    intervals, delta_intervals = cluster_intervals(test,p,old_p)
    pred = (p>=.5).astype(int)
    report = classification_report(test.label,pred,digits=4,zero_division=0)
    print('=== same test rows, threshold 0.5 ===',flush=True)
    for name in METRICS:
        print(f"{name}: {baseline[name]:.4%} -> {overall[name]:.4%}",flush=True)
    print(report,flush=True)
    print('Confusion matrix [[TN, FP], [FN, TP]]:',overall['confusion_matrix'],flush=True)
    print('ROC AUC:',overall['roc_auc'],'Average precision:',overall['average_precision'],flush=True)
    print('=== paired domain-bootstrap 95% intervals for change ===',flush=True)
    print(json.dumps(delta_intervals,indent=2),flush=True)

    test['phishing_score'], test['prediction'] = p,pred
    test['baseline_phishing_score'] = old_p
    test.to_csv(REPORTS / 'test_predictions.csv',index=False)
    errors = test[test.label != test.prediction].copy()
    errors['error'] = np.where(errors.label==1,'false_negative','false_positive')
    errors.to_csv(REPORTS / 'test_errors.csv',index=False)
    old_correct = (old_p>=.5).astype(int) == test.label.to_numpy()
    new_correct = pred == test.label.to_numpy()
    changes = {'corrected_errors':int((~old_correct&new_correct).sum()),
               'new_errors':int((old_correct&~new_correct).sum()),
               'net_fewer_errors':int(new_correct.sum()-old_correct.sum())}
    print('Error changes:',json.dumps(changes),flush=True)
    slices={}
    masks={f'source={source}':test.source==source for source in sorted(test.source.unique())}
    masks.update({
        'Kaggle (both labels)':test.source.str.contains('kaggle'),
        'depth=0':test.path_depth==0,
        'depth>=1':test.path_depth>=1,
        'short<=45 and depth=0':(test.url_length<=45)&(test.path_depth==0),
        'IP host':test.has_ip==1,
        'subdomains=0':test.subdomain_count==0,
        'subdomains>=1':test.subdomain_count>=1,
    })
    print('=== source and failure-mode slices ===',flush=True)
    for name,mask in masks.items():
        if mask.any():
            slices[name]={'before':scores(test.loc[mask,'label'],old_p[mask.to_numpy()]),
                          'after':scores(test.loc[mask,'label'],p[mask.to_numpy()])}
            print(name,json.dumps(slices[name]['after']),flush=True)
    error_domains={kind:errors.loc[errors.error==kind,'domain'].value_counts().head(10).to_dict()
                   for kind in ['false_positive','false_negative']}
    print('=== illustrative URLs; not model-selection targets ===',flush=True)
    diagnostics=[]
    for url in DIAGNOSTIC_URLS:
        with threadpool_limits(limits=4):
            probability=float(phishing_scores(model,pd.DataFrame({'url':[url]}))[0])
        item={'url':url,'phishing_score':probability,
              'label':'phishing' if probability>=.5 else 'legitimate'}
        diagnostics.append(item)
        print(json.dumps(item),flush=True)
    summary={'overall':overall,'baseline_same_test':baseline,'classification_report':report,
             'domain_bootstrap_95_percent':intervals,'paired_change_95_percent':delta_intervals,
             'error_changes':changes,'slices':slices,'top_error_domains':error_domains,
             'diagnostics':diagnostics,'model_sha256':metadata['sha256']['model.pkl'],
             'test_history':'Previously reported internal holdout; frozen during this comparison, not an untouched external benchmark.',
             'interpretation':'No dataset, label, split or threshold changes. Candidate chosen on validation only. Scores uncalibrated and labels remain uncertain.'}
    write_json(REPORTS/'evaluation.json',summary)
    validation=json.loads((REPORTS/'validation.json').read_text())
    audit=json.loads((REPORTS/'dataset_audit.json').read_text())
    lines=[
        '# PhishGuard Phase 1: richer URL model','',
        'The model uses URL text and structural measurements; no URL is fetched.',
        'Data, labels and registered-domain assignments are unchanged from the audited seven-feature baseline.',
        'Threshold remains 0.5. The test set has appeared in earlier reports: this is a controlled internal comparison, not a fresh external benchmark.','',
        '## Same-test comparison','',
        '| Metric | Seven-feature reference | Richer URL model |',
        '|---|---|---|',
    ]
    for name in METRICS:
        lines.append(f"| {name} | {baseline[name]:.2%} | {overall[name]:.2%} |")
    lines += ['',f"Test rows: {len(test):,}; {overall['benign']:,} benign and {overall['phishing']:,} phishing.",
              f"Old confusion matrix [[TN, FP], [FN, TP]]: {baseline['confusion_matrix']}",
              f"New confusion matrix [[TN, FP], [FN, TP]]: {overall['confusion_matrix']}",
              f"Corrected old errors: {changes['corrected_errors']:,}; newly introduced errors: {changes['new_errors']:,}; net fewer errors: {changes['net_fewer_errors']:,}.",
              '', '### Classification report','','```text',report.rstrip(),'```','',
              '## What changed and why','',
              '- Seven aggregate counts discarded spelling/content patterns, mapping different URLs to identical inputs.',
              '- The text model learns character sequences of lengths 3-5 with training-only TF-IDF, min_df=3, vocabulary capped at 180,000, then balanced L2 logistic regression.',
              '- The structural model measures 38 features, including separate host/path/query lengths, entropy/digits, parameters, encoding, token lengths and embedded URL indicators.',
              '- Structural learner: histogram gradient boosting, 350 iterations, learning_rate=.08, 31 leaves, min_samples_leaf=30, l2_regularization=10; no internal row-random early stopping.',
              '- Bounded comparison: text C=2 or 8; text alone, structure alone, and probability blends with text weights .25/.5/.75.',
              '- Selection: highest validation phishing F1 at .5 among candidates improving all accuracy/precision/recall/F1 and FPR versus the reference.',
              f"- Chosen: {metadata['chosen_variant']}; text weight {metadata['text_weight']}. No fit on validation or test.",
              '- Same canonical URL normalization, offline PSL, source quarantine policy and grouped split retained. No hand-crafted allowlist/blocklist, source, label, domain rank or held-out vocabulary enters inference.',
              '- Text inputs longer than 4096 characters use the first 3072 plus last 1024 for bounded sparse computation; numeric measurements use the full URL.',
              '- Source labels are used for reporting only. No suspicious-keyword score or external reputation lookup was added.','',
              '## Validation candidates','',
              '| Candidate | Accuracy | Precision | Recall | F1 | FPR |','|---|---|---|---|---|---|']
    for name,r in validation['candidates'].items():
        lines.append(f"| {name} | {r['accuracy']:.4f} | {r['precision']:.4f} | {r['recall']:.4f} | {r['f1']:.4f} | {r['false_positive_rate']:.4f} |")
    lines += ['','## Validation threshold tradeoff','',
              'Reported for inspection; the deployed threshold stays at 0.5.',
              '| Threshold | Precision | Recall | F1 | FPR |','|---|---|---|---|---|']
    for r in validation['threshold_tradeoff']:
        lines.append(f"| {r['threshold']:.1f} | {r['precision']:.4f} | {r['recall']:.4f} | {r['f1']:.4f} | {r['false_positive_rate']:.4f} |")
    lines += ['','## 95% domain-bootstrap intervals','',
              '300 paired resamples of whole registered domains. Change = richer minus reference. Negative FPR change is beneficial.',
              '| Metric | New metric interval | Change interval |','|---|---|---|']
    for name in METRICS:
        lo,hi=intervals[name];dlo,dhi=delta_intervals[name]
        lines.append(f'| {name} | {lo:.4f} to {hi:.4f} | {dlo:.4f} to {dhi:.4f} |')
    lines += ['','## Source and shape slices','',
              '| Slice | Benign | Phishing | Old recall | New recall | Old FPR | New FPR |',
              '|---|---|---|---|---|---|---|']
    for name,values in slices.items():
        old,new=values['before'],values['after']
        old_fpr='-' if old['false_positive_rate'] is None else f"{old['false_positive_rate']:.4f}"
        new_fpr='-' if new['false_positive_rate'] is None else f"{new['false_positive_rate']:.4f}"
        old_recall='-' if not old['phishing'] else f"{old['recall']:.4f}"
        new_recall='-' if not new['phishing'] else f"{new['recall']:.4f}"
        lines.append(f"| {name.replace('|','/')} | {new['benign']} | {new['phishing']} | {old_recall} | {new_recall} | {old_fpr} | {new_fpr} |")
    lines += ['','## Remaining failure modes','',
              f"- False positives remain {overall['false_positive_rate']:.2%}; missed phishing remains {1-overall['recall']:.2%}. This is not a safe-site certification.",
              f"- {audit['keyword_quarantine_rows']:,} keyword-matching benign rows remain quarantined as uncertain labels. Login/account-related text may inherit this selection bias; this benchmark does not establish accuracy on those excluded pages.",
              '- Kaggle labels are not independently adjudicated, Tranco is a popularity proxy, and PhishTank online/verified status describes the downloaded snapshot. Source and temporal bias remain.',
              '- Domain grouping prevents related domains crossing splits, but campaign templates can occur across unrelated domains. There is no independent campaign/time holdout.',
              '- Character models can learn spelling conventions and dataset artifacts. This improvement does not establish external generalization or remove the need for recent, independently labeled data.',
              '- No domain reputation, DNS, TLS, redirect resolution, page content or page-age evidence is available. An IP login page alone does not establish phishing intent.',
              '- Probabilities are uncalibrated. Text contributions are exact log-odds terms for the text component only; they are not explanations of the structural model or blended probability.',
              '- Bootstrap intervals cover domain sampling in this dataset, not label errors, future drift, or repeated development against this corpus.',
              '', '## Most concentrated errors','',
              '| Error | Registered domain | Count |','|---|---|---|']
    for kind,domains in error_domains.items():
        for domain,count in domains.items():
            lines.append(f'| {kind} | {domain} | {count} |')
    lines += ['','## Reproduce','', '```text',
              'python src/build_final_dataset.py','python src/build_features.py',
              'python src/train.py','python src/evaluate.py',
              'python -m unittest discover -s src -p "test_*.py"',
              'python -m uvicorn api:app --app-dir src --port 8000','```','',
              'Training regenerates train-only display ranges. Keep the package versions in model_metadata.json.',
              'Restart the API after training; /health reports the loaded artifact hash.',
              '', '## Evidence','',
              f"- Model SHA256: {metadata['sha256']['model.pkl']}",
              '- model_metadata.json: code/data/model hashes, library versions, chosen settings.',
              '- data/splits.csv: unchanged URL/domain/source/label/split manifest.',
              '- artifacts/richer_model/plan.json and validation.json: bounded selection protocol and every candidate.',
              '- artifacts/richer_model/baseline_model.pkl: fixed seven-feature reference on the same train rows.',
              '- artifacts/phase1/evaluation.json: complete metrics and paired intervals.',
              '- artifacts/phase1/test_predictions.csv and test_errors.csv: every outcome.',
              '- artifacts/before_richer_model/: previous model, code, dataset and reports.',
              '', 'Methods: https://scikit-learn.org/stable/modules/feature_extraction.html and https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.HistGradientBoostingClassifier.html','']
    (ROOT/'metrics.md').write_text('\n'.join(lines),encoding='utf-8')
    print('Saved metrics.md, evaluation.json and all test predictions/errors.',flush=True)


if __name__ == '__main__':
    main()
