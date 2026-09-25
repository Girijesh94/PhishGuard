import pandas as pd

df = pd.read_csv('data/malicious_phish.csv')
benign = df[df['type'] == 'benign'].copy()

suspicious_keywords = ['login', 'verify', 'secure', 'account', 'update', 'signin', 'confirm', 'wp-admin', 'cmd=']
mask = benign['url'].str.contains('|'.join(suspicious_keywords), case=False, na=False)

print(f"=== keyword filter ===")
print(f"Flagged as likely-mislabeled: {mask.sum()} out of {len(benign)}")

benign_clean = benign[~mask].copy()
print(f"Remaining benign after filter: {len(benign_clean)}")

print(f"=== domain concentration check (post-filter) ===")
domains = benign_clean['url'].str.extract(r'^(?:https?://)?([^/]+)')[0]
print(domains.value_counts().head(15))

benign_clean.to_csv('data/benign_clean.csv', index=False)
print("Saved data/benign_clean.csv")
