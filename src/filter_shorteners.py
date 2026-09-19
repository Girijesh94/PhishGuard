import pandas as pd

df = pd.read_csv('data/urls.csv')

shortener_domains = [
    'bit.ly', 'tinyurl.com', 'qrco.de', 'q-r.to', 'l.ead.me', 'l.wl.co',
    'docs.google.com', 'sites.google.com', 'new.express.adobe.com',
    't.co', 'goo.gl', 'ow.ly', 'is.gd', 'buff.ly', 'rebrand.ly'
]

df['domain'] = df['url'].str.extract(r'https?://([^/]+)')[0]

before = len(df[df['label']==1])
df = df[~df['domain'].isin(shortener_domains)]
after = len(df[df['label']==1])

print(f"Dropped {before - after} shortener-hosted phishing URLs")
print("=== label balance after filtering ===")
print(df['label'].value_counts())

print("=== top phishing domains after filtering ===")
print(df[df['label']==1]['domain'].value_counts().head(15))

df = df.drop(columns=['domain'])
df.to_csv('data/urls.csv', index=False)
print("Saved filtered data/urls.csv")
