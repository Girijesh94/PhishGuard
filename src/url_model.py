"""Offline URL text and structure models; no source, rank or label inputs."""
from urllib.parse import urlsplit
import re
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, ClassifierMixin

from features import extract_features, normalize_url, parse_host, shannon_entropy

TEXT_LIMIT = 4096


def text_view(url):
    # Bound sparse n-gram cost; structural measurements still see the full URL.
    canonical = normalize_url(url)
    return canonical if len(canonical) <= TEXT_LIMIT else canonical[:3072] + canonical[-1024:]


def structural_features(url):
    canonical = normalize_url(url)
    parsed = urlsplit('//' + canonical)
    host = parse_host(canonical)
    path, query = parsed.path, parsed.query
    tokens = [t for t in re.split(r'[^a-zA-Z0-9]+', canonical) if t]
    result = {k: v for k, v in extract_features(canonical).items() if k != 'has_https'}
    for name, part in [('host', host), ('path', path), ('query', query)]:
        result[name + '_length'] = len(part)
        result[name + '_entropy'] = shannon_entropy(part)
        result[name + '_digit_ratio'] = sum(c.isdigit() for c in part) / max(len(part), 1)
        result[name + '_hyphens'] = part.count('-')
        result[name + '_dots'] = part.count('.')
    result.update(
        query_parameters=query.count('&') + int(bool(query)),
        equals_count=query.count('='),
        percent_count=canonical.count('%'),
        at_count=canonical.count('@'),
        underscore_count=canonical.count('_'),
        fragment_length=len(parsed.fragment),
        has_port=int(':' in parsed.netloc.rsplit('@', 1)[-1].replace('[' + host + ']', '')),
        host_label_max=max(map(len, host.split('.')), default=0),
        path_segment_max=max(map(len, path.split('/')), default=0),
        token_count=len(tokens),
        token_length_max=max(map(len, tokens), default=0),
        longest_digit_run=max((len(m) for m in re.findall(r'\d+', canonical)), default=0),
        upper_ratio=sum(c.isupper() for c in path + query) / max(len(path + query), 1),
        encoded_octets=len(re.findall(r'%[0-9a-fA-F]{2}', canonical)),
        embedded_http=len(re.findall(r'https?[:%]', path + query, flags=re.I)),
        path_extension_length=len(path.rsplit('.', 1)[-1]) if '.' in path.rsplit('/', 1)[-1] else 0,
    )
    return result


def structural_matrix(urls):
    return pd.DataFrame.from_records([structural_features(u) for u in urls])


class URLClassifier(ClassifierMixin, BaseEstimator):
    """Blend a text logistic model and a structure gradient-boosting model."""
    def __init__(self, vectorizer=None, text_model=None, structure_model=None, text_weight=1.0):
        self.vectorizer = vectorizer
        self.text_model = text_model
        self.structure_model = structure_model
        self.text_weight = text_weight
        self.classes_ = np.array([0, 1])
        self.feature_names_in_ = np.array(['url'], dtype=object)
        self.n_features_in_ = 1

    def component_scores(self, X):
        if list(X.columns) != ['url']:
            raise ValueError("URLClassifier requires exactly one column: 'url'")
        urls = X.url.tolist()
        text = None
        structure = None
        if self.text_model is not None and self.text_weight > 0:
            matrix = self.vectorizer.transform([text_view(u) for u in urls])
            text = self.text_model.predict_proba(matrix)[:, list(self.text_model.classes_).index(1)]
        if self.structure_model is not None and self.text_weight < 1:
            matrix = structural_matrix(urls)
            structure = self.structure_model.predict_proba(matrix)[:, list(self.structure_model.classes_).index(1)]
        return text, structure

    def predict_proba(self, X):
        text, structure = self.component_scores(X)
        if text is None:
            probability = structure
        elif structure is None:
            probability = text
        else:
            probability = self.text_weight * text + (1 - self.text_weight) * structure
        if probability is None:
            raise ValueError('No fitted component is active')
        return np.column_stack([1 - probability, probability])

    def predict(self, X):
        return (self.predict_proba(X)[:, 1] >= .5).astype(int)

    def text_contributions(self, url, limit=3):
        """Exact additive log-odds contributions in the TEXT component only."""
        if self.text_model is None or self.text_weight == 0:
            return []
        row = self.vectorizer.transform([text_view(url)]).tocsr()
        values = row.data * self.text_model.coef_[0, row.indices]
        order = np.argsort(-np.abs(values))[:limit]
        terms = self.vectorizer.get_feature_names_out()
        return [
            {'feature': 'text:' + terms[row.indices[i]], 'value': float(row.data[i]),
             'contribution': round(float(values[i]), 4)}
            for i in order
        ]
