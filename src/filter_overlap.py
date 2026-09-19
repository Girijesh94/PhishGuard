import pandas as pd

df = pd.read_csv('data/urls.csv')
df['domain'] = df['url'].str.extract(r'https?://([^/]+)')[0]

legit_domains = set(df[df['label']==0]['domain'])
phish_domains = set(df[df['label']==1]['domain'])
overlap = legit_domains & phish_domains

print(f"Domains appearing in both classes: {len(overlap)}")
print(sorted(overlap)[:30])

before = len(df[df['label']==1])
df = df[~((df['label']==1) & (df['domain'].isin(overlap)))]
after = len(df[df['label']==1])

print(f"Dropped {before-after} additional phishing rows sharing a domain with legitimate Tranco entries")
print("=== label balance after overlap filtering ===")
print(df['label'].value_counts())

df = df.drop(columns=['domain'])
df.to_csv('data/urls.csv', index=False)
print("Saved data/urls.csv")
