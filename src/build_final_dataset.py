"""Provenance-preserving research dataset without host-wide exclusions."""
import pandas as pd
from features import domain_group, normalize_url
from pipeline import DATA, REPORTS, digest, write_json

N_TRANCO_BACKFILL = 12000
SUSPICIOUS_KEYWORDS = ['login', 'verify', 'secure', 'account', 'update',
                       'signin', 'confirm', 'wp-admin', 'cmd=']


def resolve_rows(df):
    """Collapse identical canonical URLs; quarantine BOTH conflicting labels."""
    df = df.copy()
    df['url'] = df.raw_url.map(normalize_url)
    def parse_domain(url):
        try:
            domain = domain_group(url)
            return domain, '' if domain else 'Empty hostname'
        except ValueError as exc:
            return '', str(exc)
    parsed = df.url.map(parse_domain)
    df['domain'] = parsed.map(lambda pair: pair[0])
    df['exclusion_reason'] = parsed.map(lambda pair: pair[1])
    valid = df[df.exclusion_reason.eq('')].copy()
    conflicts = valid.groupby('url').label.nunique()
    valid.loc[valid.url.isin(conflicts[conflicts > 1].index), 'exclusion_reason'] = 'conflicting_labels'
    quarantine = pd.concat([df[~df.exclusion_reason.eq('')], valid[~valid.exclusion_reason.eq('')]])
    usable = valid[valid.exclusion_reason.eq('')]
    result = usable.groupby('url', as_index=False, sort=True).agg(
        raw_url=('raw_url', 'first'), label=('label', 'first'),
        source=('source', lambda s: '|'.join(sorted(set(s)))),
        domain=('domain', 'first'))
    return result, quarantine


def main():
    REPORTS.mkdir(parents=True, exist_ok=True)
    kaggle = pd.read_csv(DATA / 'malicious_phish.csv')
    benign = kaggle[kaggle.type == 'benign'][['url']].copy()
    # Existing keyword exclusion retained as UNCERTAIN labels, not proven phish.
    flagged = benign.url.str.contains('|'.join(SUSPICIOUS_KEYWORDS), case=False, na=False)
    benign[flagged].to_csv(REPORTS / 'keyword_quarantine.csv', index=False)
    benign = benign[~flagged]
    tank = pd.read_csv(DATA / 'verified_online.csv')
    tank = tank[(tank.verified == 'yes') & (tank.online == 'yes')][['url']].copy()
    benign = benign.sample(n=min(2 * len(tank), len(benign)), random_state=42)
    kaggle_phish = kaggle[kaggle.type == 'phishing'][['url']].copy()
    tranco = pd.read_csv(DATA / 'tranco_38KVL.csv', header=None, names=['rank', 'domain']).head(N_TRANCO_BACKFILL)
    parts = []
    for frame, label, source in [
        (benign, 0, 'kaggle_benign'), (kaggle_phish, 1, 'kaggle_phishing'),
        (tank, 1, 'phishtank'),
        (pd.DataFrame({'url': 'http://' + tranco.domain}), 0, 'tranco'),
    ]:
        parts.append(frame.rename(columns={'url': 'raw_url'}).assign(label=label, source=source))
    raw = pd.concat(parts, ignore_index=True)
    df, quarantine = resolve_rows(raw)
    quarantine.to_csv(REPORTS / 'label_conflicts.csv', index=False)
    df = df.sample(frac=1, random_state=42).reset_index(drop=True)
    df.to_csv(DATA / 'urls.csv', index=False)
    audit = {
        'raw_rows': len(raw), 'retained_rows': len(df),
        'keyword_quarantine_rows': int(flagged.sum()),
        'quarantined_rows': len(quarantine),
        'conflicting_rows': int(quarantine.exclusion_reason.eq('conflicting_labels').sum()),
        'invalid_url_rows': int(quarantine.exclusion_reason.ne('conflicting_labels').sum()),
        'conflicting_urls': quarantine.loc[quarantine.exclusion_reason.eq('conflicting_labels'), 'url'].nunique(),
        'duplicate_rows_collapsed': len(raw) - len(quarantine) - len(df),
        'label_counts': {str(k): int(v) for k, v in df.label.value_counts().items()},
        'source_counts': df.source.value_counts().to_dict(),
        'input_sha256': {n: digest(DATA / n) for n in ['malicious_phish.csv', 'verified_online.csv', 'tranco_38KVL.csv']},
        'policy': 'No host-wide overlap or platform exclusions. Conflicting URL labels quarantined symmetrically. Keyword exclusions are uncertain labels. Tranco is a popularity proxy.',
    }
    write_json(REPORTS / 'dataset_audit.json', audit)
    print('Keyword-matching benign rows quarantined (NOT proven phishing):', int(flagged.sum()))
    print('Conflicting rows quarantined:', audit['conflicting_rows'], 'across', audit['conflicting_urls'], 'URLs')
    print('Malformed URL rows quarantined:', audit['invalid_url_rows'])
    print('Same-label duplicate rows collapsed:', audit['duplicate_rows_collapsed'])
    print('No verified phishing removed merely for sharing a benign host/platform.')
    print('=== label balance ===')
    print(df.label.value_counts())
    print('=== source balance ===')
    print(df.source.value_counts())
    print('Saved', DATA / 'urls.csv')


if __name__ == '__main__':
    main()
