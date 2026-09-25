"""Display ranges fitted on TRAINING rows only (not prediction inputs)."""
import json
import pandas as pd
from pipeline import DATA, ROOT, FEATURES, split_for_domain, write_json


def compute_ranges(frame):
    train = frame[frame.domain.map(split_for_domain) == 'train']
    if train.empty:
        raise ValueError('No training rows for feature ranges')
    return {col: {'min': float(train[col].min()), 'max': float(train[col].max())}
            for col in FEATURES}


def main():
    ranges = compute_ranges(pd.read_csv(DATA / 'features.csv'))
    write_json(ROOT / 'feature_ranges.json', ranges)
    print(json.dumps(ranges, indent=2))


if __name__ == '__main__':
    main()
