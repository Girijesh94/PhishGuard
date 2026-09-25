import unittest
import tempfile
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import HistGradientBoostingClassifier
from threadpoolctl import threadpool_limits
from url_model import URLClassifier, structural_features, structural_matrix, text_view, TEXT_LIMIT


class URLModelTests(unittest.TestCase):
    def test_scheme_and_www_parity_for_every_new_feature(self):
        urls = ['example.com/A?q=Test', 'http://example.com/A?q=Test',
                'https://www.example.com/A?q=Test', '//www.example.com/A?q=Test']
        for url in urls:
            self.assertEqual(structural_features(url), structural_features(urls[0]))
            self.assertEqual(text_view(url), text_view(urls[0]))

    def test_host_path_and_query_are_measured_separately(self):
        a = structural_features('http://host.example/a/b?q=123&x=4#Tail')
        self.assertEqual(a['host_length'], len('host.example'))
        self.assertEqual(a['path_length'], 4)
        self.assertEqual(a['query_parameters'], 2)
        self.assertEqual(a['fragment_length'], 4)
        self.assertEqual(a['longest_digit_run'], 3)
        self.assertEqual(a['path_depth'], 2)
        self.assertNotIn('has_https', a)

    def test_text_cost_bounded_without_truncating_numeric_features(self):
        url = 'example.com/' + 'a' * 5000 + '?token=1234'
        self.assertEqual(len(text_view(url)), TEXT_LIMIT)
        self.assertTrue(text_view(url).endswith('?token=1234'))
        self.assertEqual(structural_features(url)['url_length'], len(url))

    def test_ports_and_ipv6(self):
        self.assertEqual(structural_features('http://[2001:db8::1]/')['has_port'], 0)
        self.assertEqual(structural_features('http://[2001:db8::1]:8443/')['has_port'], 1)
        self.assertEqual(structural_features('example.com:8080/a')['has_port'], 1)

    def test_serialized_blend_and_exact_text_explanation(self):
        urls = ['alpha.org/news', 'beta.net/about', 'gamma.org/help', 'delta.net/info',
                'account-one.test/verify', 'account-two.test/login',
                'account-three.test/verify', 'account-four.test/login']
        y = np.array([0,0,0,0,1,1,1,1])
        vec = TfidfVectorizer(analyzer='char', ngram_range=(3,5))
        text = vec.fit_transform([text_view(u) for u in urls])
        linear = LogisticRegression(solver='liblinear').fit(text, y)
        numeric = structural_matrix(urls)
        with threadpool_limits(limits=1):
            trees = HistGradientBoostingClassifier(max_iter=5, min_samples_leaf=1).fit(numeric, y)
            model = URLClassifier(vec, linear, trees, .75)
            frame = pd.DataFrame({'url': urls})
            expected = .75 * linear.predict_proba(text)[:,1] + .25 * trees.predict_proba(numeric)[:,1]
            np.testing.assert_allclose(model.predict_proba(frame)[:,1], expected)
            with tempfile.TemporaryDirectory() as temp:
                path = Path(temp)/'model.pkl'
                joblib.dump(model, path)
                loaded = joblib.load(path)
                np.testing.assert_allclose(loaded.predict_proba(frame)[:,1], expected)
        with self.assertRaisesRegex(ValueError, 'exactly one column'):
            model.predict_proba(frame.assign(label=y))
        contributions = model.text_contributions(urls[0], limit=10000)
        # API rounds display contributions to four decimals.
        total = sum(x['contribution'] for x in contributions) + linear.intercept_[0]
        self.assertAlmostEqual(total, linear.decision_function(text[:1])[0], delta=.01)


class ComparisonTests(unittest.TestCase):
    def test_paired_bootstrap_uses_same_domains_for_both_models(self):
        from evaluate import cluster_intervals
        frame = pd.DataFrame({'domain':['one.test','one.test','two.test','two.test'],
                              'label':[0,1,0,1]})
        new = np.array([.1,.9,.1,.9])
        old = 1-new
        current, delta = cluster_intervals(frame,new,old,repeats=10)
        for metric in ['accuracy','precision','recall','f1']:
            self.assertEqual(current[metric],[1.,1.])
            self.assertEqual(delta[metric],[1.,1.])
        self.assertEqual(delta['false_positive_rate'],[-1.,-1.])
        _,same=cluster_intervals(frame,new,new,repeats=10)
        for bounds in same.values(): self.assertEqual(bounds,[0.,0.])

    def test_richer_extractor_change_rejected_before_unpickling(self):
        from unittest.mock import patch
        from pipeline import digest,write_json,load_artifact
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'src').mkdir()
            names=['model.pkl','src/features.py','feature_ranges.json','src/url_model.py']
            for name in names: (root/name).write_bytes(b'original')
            write_json(root/'model_metadata.json',{
                'model_kind':'url_text_structure',
                'sha256':{name:digest(root/name) for name in names}})
            (root/'src/url_model.py').write_bytes(b'changed')
            with patch('pipeline.ROOT',root):
                with self.assertRaisesRegex(ValueError,'Stale artifact'):
                    load_artifact()


if __name__ == '__main__':
    unittest.main()
