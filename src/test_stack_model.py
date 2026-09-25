import unittest
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from stack_model import meta_features,StackedURLClassifier


class FixedComponents:
    def component_scores(self, X):
        return X.text.to_numpy(),X.structure.to_numpy()
    def text_contributions(self,url,limit=3):
        return [{'feature':'text:demo','value':1.,'contribution':.2}]


class StackingTests(unittest.TestCase):
    def test_logit_features_are_finite_at_boundaries(self):
        frame=meta_features(np.array([0.,1.,.5]),np.array([1.,0.,.5]))
        self.assertTrue(np.isfinite(frame.to_numpy()).all())
        self.assertEqual(frame.iloc[2].tolist(),[0.,0.])
        self.assertLess(frame.iloc[0,0],0)
        self.assertGreater(frame.iloc[0,1],0)

    def test_numeric_features_align_by_position(self):
        numeric=pd.DataFrame({'length':[10.,20.]},index=[90,20])
        frame=meta_features(np.array([.1,.9]),np.array([.2,.8]),numeric)
        self.assertEqual(frame.length.tolist(),[10.,20.])
        self.assertFalse(frame.isna().any().any())

    def test_stacked_probability_matches_meta_estimator(self):
        frame=pd.DataFrame({'text':[.1,.2,.8,.9], 'structure':[.2,.1,.9,.8]})
        X=meta_features(frame.text.to_numpy(),frame.structure.to_numpy())
        meta=LogisticRegression().fit(X,[0,0,1,1])
        model=StackedURLClassifier(FixedComponents(),meta)
        np.testing.assert_allclose(model.predict_proba(frame),meta.predict_proba(X))
        np.testing.assert_array_equal(model.predict(frame),[0,0,1,1])
        self.assertEqual(model.text_contributions('example.com')[0]['feature'],'text:demo')


if __name__=='__main__':
    unittest.main()
