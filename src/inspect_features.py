import pandas as pd
pd.set_option('display.max_columns', None)
pd.set_option('display.width', None)

df = pd.read_csv('data/features.csv')
print(df.sample(10, random_state=2).to_string())
print()
print(df.describe())
