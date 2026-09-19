import pandas as pd
from features import extract_features

df = pd.read_csv('data/urls.csv')

feature_df = df['url'].apply(extract_features).apply(pd.Series)
result = pd.concat([df, feature_df], axis=1)

print("=== shape ===")
print(result.shape)
print("=== null check ===")
print(result.isnull().sum())
print("=== sample rows ===")
print(result.sample(5, random_state=1))

result.to_csv('data/features.csv', index=False)
print("Saved data/features.csv")
