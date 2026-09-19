# Model Evaluation

## Final Metrics (7 features, has_https excluded)

              precision    recall  f1-score   support
           0       0.99      1.00      0.99     30300
           1       0.99      0.96      0.97     10612
    accuracy                           0.99     40912

Confusion Matrix:
[[30208    92]
 [  445 10167]]

Feature Importances:
subdomain_count: 0.3582
url_length: 0.2789
path_depth: 0.1547
entropy: 0.1499
digit_ratio: 0.0375
special_chars: 0.0204
has_ip: 0.0003

## Known Limitations

Legitimate URLs were sourced from the Tranco top-1M list as bare domains (no path/subdomain data available at scale), while phishing URLs came from PhishTank as full real-world URLs. This creates a structural asymmetry: features like subdomain_count, url_length, and path_depth may partially reflect this source difference rather than a purely learned phishing signal. has_https was excluded entirely after confirming it was a pure artifact (100% of Tranco URLs were assigned http:// during construction, an artificial value, not observed reality). The remaining skew in subdomain_count etc. is a known limitation of this dataset combination, not fully resolved in this version.
