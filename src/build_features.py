import pandas as pd
from features import extract_features, normalize_url
from pipeline import DATA, REPORTS, digest, write_json, ROOT


def main():
    df = pd.read_csv(DATA / 'urls.csv')
    if not df.url.map(normalize_url).eq(df.url).all():
        raise ValueError('urls.csv is not normalized; rerun build_final_dataset.py')
    features = pd.DataFrame.from_records(df.url.map(extract_features))
    result = pd.concat([df, features], axis=1)
    if result.isna().any().any():
        raise ValueError('Null fields in extracted dataset')
    result.to_csv(DATA / 'features.csv', index=False)
    write_json(REPORTS / 'features_manifest.json', {
        'urls_sha256': digest(DATA / 'urls.csv'),
        'features_sha256': digest(DATA / 'features.csv'),
        'extractor_sha256': digest(ROOT / 'src/features.py'),
    })
    print('=== shape ===')
    print(result.shape)
    print('=== null check ===')
    print(result.isnull().sum())
    print('Saved', DATA / 'features.csv')


if __name__ == '__main__':
    main()
