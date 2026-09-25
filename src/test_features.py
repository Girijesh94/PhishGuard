import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd

from features import (domain_group, extract_features, has_ip_address, normalize_url,
                      parse_host, path_depth)
from build_final_dataset import resolve_rows
from pipeline import (FEATURES, assert_disjoint, digest, load_artifact,
                      phishing_scores, scores, split_for_domain, write_json)


class FeatureTests(unittest.TestCase):
    def test_train_serve_spelling_parity(self):
        variants = ['google.com', 'www.google.com', 'http://google.com',
                    'https://www.google.com/', '//Google.com/',
                    'https://www.www.google.com']
        for value in variants:
            self.assertEqual(normalize_url(value), 'google.com')
            self.assertEqual(extract_features(value), extract_features('google.com'))
            self.assertEqual(normalize_url(normalize_url(value)), normalize_url(value))

    def test_query_and_path_are_not_host_or_depth(self):
        value = 'https://User@WWW.Example.com:8443/A/B?q=/C#Fragment'
        self.assertEqual(parse_host(value), 'example.com')
        self.assertEqual(path_depth(value), 2)
        self.assertIn('/A/B?q=/C#Fragment', normalize_url(value))
        self.assertEqual(path_depth('example.com?q=/A/B'), 0)

    def test_ipv4_ipv6_and_invalid_ip(self):
        self.assertEqual(has_ip_address('http://192.168.1.1/login'), 1)
        self.assertEqual(has_ip_address('http://[2001:db8::1]:8080/login'), 1)
        self.assertEqual(has_ip_address('http://999.999.999.999'), 0)
        self.assertEqual(extract_features('http://[2001:db8::1]/login')['subdomain_count'], 0)

    def test_psl_groups_related_hosts_and_whole_platforms(self):
        self.assertEqual(domain_group('a.example.co.uk/path'), 'example.co.uk')
        self.assertEqual(domain_group('b.example.co.uk'), 'example.co.uk')
        self.assertEqual(domain_group('tenant.blogspot.com'), 'blogspot.com')
        self.assertEqual(domain_group('192.168.1.1/a'), '192.168.1.1')

    def test_entropy_reproducible_across_python_processes(self):
        code = "from features import extract_features; print(repr(extract_features('a-example.com/A1B2?a=xyz')))"
        outputs = []
        for seed in ['1', '42']:
            env = dict(os.environ, PYTHONHASHSEED=seed)
            outputs.append(subprocess.check_output([sys.executable, '-c', code],
                           cwd=Path(__file__).parent, env=env, text=True))
        self.assertEqual(*outputs)


class DatasetTests(unittest.TestCase):
    def test_conflicts_removed_both_sides_and_same_host_phishing_retained(self):
        raw = pd.DataFrame([
            ('http://example.com/', 0, 'tranco'),
            ('https://www.example.com', 1, 'phishtank'),
            ('safe.com/', 0, 'tranco'),
            ('safe.com/login/phish', 1, 'phishtank'),
            ('safe.com/login/phish', 1, 'kaggle_phishing'),
            ('http://[broken', 1, 'phishtank'),
        ], columns=['raw_url', 'label', 'source'])
        usable, quarantine = resolve_rows(raw)
        self.assertEqual(set(usable.url), {'safe.com', 'safe.com/login/phish'})
        self.assertEqual(len(quarantine), 3)
        row = usable[usable.label == 1].iloc[0]
        self.assertEqual(row.source, 'kaggle_phishing|phishtank')

    def test_split_is_order_independent_and_registered_domain_disjoint(self):
        frame = pd.DataFrame({'url': [f'{i}.example-{j}.com' for j in range(100) for i in range(2)],
                              'label': [i for j in range(100) for i in range(2)]})
        frame['domain'] = frame.url.map(domain_group)
        frame['split'] = frame.domain.map(split_for_domain)
        assert_disjoint(frame)
        shuffled = frame.sample(frac=1, random_state=2)
        self.assertTrue(shuffled.domain.map(split_for_domain).equals(shuffled.split))
        bad = frame.copy()
        bad.loc[0, 'split'] = 'test' if bad.loc[1, 'split'] != 'test' else 'train'
        with self.assertRaises(ValueError):
            assert_disjoint(bad)

    def test_exact_threshold_and_class_order(self):
        report = scores([0, 1], [.49, .5])
        self.assertEqual(report['confusion_matrix'], [[1, 0], [0, 1]])
        class ReversedModel:
            classes_ = np.array([1, 0])
            def predict_proba(self, X):
                return np.array([[.7, .3]])
        np.testing.assert_array_equal(phishing_scores(ReversedModel(), None), [.7])

    def test_stale_model_rejected_before_unpickling(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'model.pkl').write_bytes(b'original')
            write_json(root / 'model_metadata.json',
                       {'sha256': {'model.pkl': digest(root / 'model.pkl')}})
            (root / 'model.pkl').write_bytes(b'changed')
            with patch('pipeline.ROOT', root):
                with self.assertRaisesRegex(ValueError, 'Stale artifact'):
                    load_artifact()


if __name__ == '__main__':
    unittest.main()
