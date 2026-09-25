# PhishGuard Phase 1: richer URL model

The model uses URL text and structural measurements; no URL is fetched.
Data, labels and registered-domain assignments are unchanged from the audited seven-feature baseline.
Threshold remains 0.5. The test set has appeared in earlier reports: this is a controlled internal comparison, not a fresh external benchmark.

## Same-test comparison

| Metric | Seven-feature reference | Richer URL model |
|---|---|---|
| accuracy | 70.90% | 88.24% |
| precision | 67.09% | 86.71% |
| recall | 74.39% | 88.47% |
| f1 | 70.55% | 87.58% |
| false_positive_rate | 32.18% | 11.96% |

Test rows: 70,494; 37,458 benign and 33,036 phishing.
Old confusion matrix [[TN, FP], [FN, TP]]: [[25405, 12053], [8460, 24576]]
New confusion matrix [[TN, FP], [FN, TP]]: [[32979, 4479], [3809, 29227]]
Corrected old errors: 15,182; newly introduced errors: 2,957; net fewer errors: 12,225.

### Classification report

```text
              precision    recall  f1-score   support

           0     0.8965    0.8804    0.8884     37458
           1     0.8671    0.8847    0.8758     33036

    accuracy                         0.8824     70494
   macro avg     0.8818    0.8826    0.8821     70494
weighted avg     0.8827    0.8824    0.8825     70494
```

## What changed and why

- Seven aggregate counts discarded spelling/content patterns, mapping different URLs to identical inputs.
- The text model learns character sequences of lengths 3-5 with training-only TF-IDF, min_df=3, vocabulary capped at 180,000, then balanced L2 logistic regression.
- The structural model measures 38 features, including separate host/path/query lengths, entropy/digits, parameters, encoding, token lengths and embedded URL indicators.
- Structural learner: histogram gradient boosting, 350 iterations, learning_rate=.08, 31 leaves, min_samples_leaf=30, l2_regularization=10; no internal row-random early stopping.
- Bounded comparison: text C=2 or 8; text alone, structure alone, and probability blends with text weights .25/.5/.75.
- Selection: highest validation phishing F1 at .5 among candidates improving all accuracy/precision/recall/F1 and FPR versus the reference.
- Chosen: char_C2_blend0.5; text weight 0.5. No fit on validation or test.
- Same canonical URL normalization, offline PSL, source quarantine policy and grouped split retained. No hand-crafted allowlist/blocklist, source, label, domain rank or held-out vocabulary enters inference.
- Text inputs longer than 4096 characters use the first 3072 plus last 1024 for bounded sparse computation; numeric measurements use the full URL.
- Source labels are used for reporting only. No suspicious-keyword score or external reputation lookup was added.

## Validation candidates

| Candidate | Accuracy | Precision | Recall | F1 | FPR |
|---|---|---|---|---|---|
| structure | 0.7527 | 0.7823 | 0.7864 | 0.7843 | 0.2923 |
| char_C2 | 0.8260 | 0.8505 | 0.8441 | 0.8473 | 0.1982 |
| char_C2_blend0.25 | 0.7893 | 0.8096 | 0.8258 | 0.8176 | 0.2594 |
| char_C2_blend0.5 | 0.8542 | 0.8546 | 0.8979 | 0.8757 | 0.2041 |
| char_C2_blend0.75 | 0.8473 | 0.8583 | 0.8779 | 0.8680 | 0.1937 |
| char_C8 | 0.8192 | 0.8493 | 0.8313 | 0.8402 | 0.1970 |
| char_C8_blend0.25 | 0.7950 | 0.8138 | 0.8320 | 0.8228 | 0.2544 |
| char_C8_blend0.5 | 0.8526 | 0.8585 | 0.8888 | 0.8734 | 0.1957 |
| char_C8_blend0.75 | 0.8341 | 0.8563 | 0.8530 | 0.8546 | 0.1913 |

## Validation threshold tradeoff

Reported for inspection; the deployed threshold stays at 0.5.
| Threshold | Precision | Recall | F1 | FPR |
|---|---|---|---|---|
| 0.1 | 0.6436 | 0.9984 | 0.7827 | 0.7386 |
| 0.2 | 0.6888 | 0.9932 | 0.8135 | 0.5994 |
| 0.3 | 0.7398 | 0.9761 | 0.8417 | 0.4587 |
| 0.4 | 0.8012 | 0.9492 | 0.8689 | 0.3147 |
| 0.5 | 0.8546 | 0.8979 | 0.8757 | 0.2041 |
| 0.6 | 0.8941 | 0.7713 | 0.8282 | 0.1221 |
| 0.7 | 0.9431 | 0.6301 | 0.7554 | 0.0508 |
| 0.8 | 0.9788 | 0.4792 | 0.6434 | 0.0139 |
| 0.9 | 0.9968 | 0.2407 | 0.3877 | 0.0010 |

## 95% domain-bootstrap intervals

300 paired resamples of whole registered domains. Change = richer minus reference. Negative FPR change is beneficial.
| Metric | New metric interval | Change interval |
|---|---|---|
| accuracy | 0.8567 to 0.9063 | 0.1193 to 0.2636 |
| precision | 0.7986 to 0.9165 | 0.0935 to 0.3458 |
| recall | 0.8331 to 0.9260 | 0.1023 to 0.1804 |
| f1 | 0.8169 to 0.9196 | 0.1068 to 0.2648 |
| false_positive_rate | 0.0915 to 0.1488 | -0.3396 to -0.1100 |

## Source and shape slices

| Slice | Benign | Phishing | Old recall | New recall | Old FPR | New FPR |
|---|---|---|---|---|---|---|
| source=kaggle_benign | 35109 | 0 | - | - | 0.3362 | 0.1154 |
| source=kaggle_benign/tranco | 22 | 0 | - | - | 0.0455 | 0.0455 |
| source=kaggle_phishing | 0 | 17173 | 0.6109 | 0.8015 | - | - |
| source=kaggle_phishing/phishtank | 0 | 20 | 0.7000 | 0.8500 | - | - |
| source=phishtank | 0 | 15843 | 0.8882 | 0.9749 | - | - |
| source=tranco | 2327 | 0 | - | - | 0.1074 | 0.1839 |
| Kaggle (both labels) | 35131 | 17193 | 0.6110 | 0.8015 | 0.3360 | 0.1153 |
| depth=0 | 7276 | 12813 | 0.7536 | 0.8743 | 0.4114 | 0.2298 |
| depth>=1 | 30182 | 20223 | 0.7378 | 0.8913 | 0.3002 | 0.0930 |
| short<=45 and depth=0 | 7179 | 12103 | 0.7418 | 0.8677 | 0.4091 | 0.2279 |
| IP host | 5 | 82 | 1.0000 | 1.0000 | 1.0000 | 0.6000 |
| subdomains=0 | 30206 | 18830 | 0.6705 | 0.8333 | 0.2825 | 0.0981 |
| subdomains>=1 | 7252 | 14206 | 0.8413 | 0.9528 | 0.4855 | 0.2089 |

## Remaining failure modes

- False positives remain 11.96%; missed phishing remains 11.53%. This is not a safe-site certification.
- 22,751 keyword-matching benign rows remain quarantined as uncertain labels. Login/account-related text may inherit this selection bias; this benchmark does not establish accuracy on those excluded pages.
- Kaggle labels are not independently adjudicated, Tranco is a popularity proxy, and PhishTank online/verified status describes the downloaded snapshot. Source and temporal bias remain.
- Domain grouping prevents related domains crossing splits, but campaign templates can occur across unrelated domains. There is no independent campaign/time holdout.
- Character models can learn spelling conventions and dataset artifacts. This improvement does not establish external generalization or remove the need for recent, independently labeled data.
- No domain reputation, DNS, TLS, redirect resolution, page content or page-age evidence is available. An IP login page alone does not establish phishing intent.
- Probabilities are uncalibrated. Text contributions are exact log-odds terms for the text component only; they are not explanations of the structural model or blended probability.
- Bootstrap intervals cover domain sampling in this dataset, not label errors, future drift, or repeated development against this corpus.

## Most concentrated errors

| Error | Registered domain | Count |
|---|---|---|
| false_positive | blogspot.com | 619 |
| false_positive | twitter.com | 182 |
| false_positive | babinet.cz | 116 |
| false_positive | ecnavi.jp | 65 |
| false_positive | villakidsbuffetinfantil.com | 46 |
| false_positive | amazon.com | 46 |
| false_positive | weebly.com | 41 |
| false_positive | allegro.pl | 39 |
| false_positive | loot.co.za | 34 |
| false_positive | cdbaby.com | 32 |
| false_negative | blogspot.com | 166 |
| false_negative | wired.com | 157 |
| false_negative | neopets.com | 68 |
| false_negative | powr.io | 56 |
| false_negative | amazon.com | 37 |
| false_negative | computerworld.com | 35 |
| false_negative | informit.com | 35 |
| false_negative | bbc.co.uk | 34 |
| false_negative | beget.tech | 34 |
| false_negative | sans.org | 25 |

## Reproduce

```text
python src/build_final_dataset.py
python src/build_features.py
python src/train.py
python src/evaluate.py
python -m unittest discover -s src -p "test_*.py"
python -m uvicorn api:app --app-dir src --port 8000
```

Training regenerates train-only display ranges. Keep the package versions in model_metadata.json.
Restart the API after training; /health reports the loaded artifact hash.

## Evidence

- Model SHA256: c9cf4c89432fb04c9ae67d88b521e6ac0169daaf2e6f2cad1133352cc805a894
- model_metadata.json: code/data/model hashes, library versions, chosen settings.
- data/splits.csv: unchanged URL/domain/source/label/split manifest.
- artifacts/richer_model/plan.json and validation.json: bounded selection protocol and every candidate.
- artifacts/richer_model/baseline_model.pkl: fixed seven-feature reference on the same train rows.
- artifacts/phase1/evaluation.json: complete metrics and paired intervals.
- artifacts/phase1/test_predictions.csv and test_errors.csv: every outcome.
- artifacts/before_richer_model/: previous model, code, dataset and reports.

Methods: https://scikit-learn.org/stable/modules/feature_extraction.html and https://scikit-learn.org/stable/modules/generated/sklearn.ensemble.HistGradientBoostingClassifier.html
