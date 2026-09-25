"""Meta-classification of out-of-fold-trained URL component scores."""
import numpy as np
import pandas as pd
from sklearn.base import ClassifierMixin, BaseEstimator
from url_model import structural_matrix


def meta_features(text, structure, numeric=None):
    columns = {
        'text_logit': np.log(np.clip(text,1e-6,1-1e-6)/np.clip(1-text,1e-6,1-1e-6)),
        'structure_logit': np.log(np.clip(structure,1e-6,1-1e-6)/np.clip(1-structure,1e-6,1-1e-6)),
    }
    frame = pd.DataFrame(columns)
    if numeric is not None:
        frame = pd.concat([frame,numeric.reset_index(drop=True)],axis=1)
    return frame


class StackedURLClassifier(ClassifierMixin, BaseEstimator):
    def __init__(self, base_model, meta_model, include_structure=False):
        self.base_model=base_model
        self.meta_model=meta_model
        self.include_structure=include_structure
        self.classes_=np.array([0,1])
        self.feature_names_in_=np.array(['url'],dtype=object)
        self.n_features_in_=1

    def predict_proba(self,X):
        text,structure=self.base_model.component_scores(X)
        numeric=structural_matrix(X.url) if self.include_structure else None
        return self.meta_model.predict_proba(meta_features(text,structure,numeric))

    def predict(self,X):
        return (self.predict_proba(X)[:,1]>=.5).astype(int)

    def text_contributions(self,url,limit=3):
        return self.base_model.text_contributions(url,limit)
