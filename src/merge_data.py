import pandas as pd

tranco = pd.read_csv('data/tranco_38KVL.csv', header=None, names=['rank', 'domain'])
phish = pd.read_csv('data/verified_online.csv')

print("=== verified counts ===")
print(phish['verified'].value_counts())
print("=== online counts ===")
print(phish['online'].value_counts())
print("=== total phish rows ===")
print(len(phish))

phish_f = phish[(phish['verified'] == 'yes') & (phish['online'] == 'yes')]
phish_f = phish_f[['url']].copy()
phish_f['label'] = 1

tranco['url'] = 'http://' + tranco['domain']
tranco['label'] = 0

n = len(phish_f)
tranco_sample = tranco.sample(n=min(n*2, len(tranco)), random_state=42)

df = pd.concat([tranco_sample[['url','label']], phish_f[['url','label']]], ignore_index=True)
df = df.sample(frac=1, random_state=42).reset_index(drop=True)
df.to_csv('data/urls.csv', index=False)

print("=== label balance ===")
print(df['label'].value_counts())

print("=== top phishing domains ===")
print(df[df['label']==1]['url'].str.extract(r'https?://([^/]+)')[0].value_counts().head(10))
