"""Train a combiner from group-disjoint out-of-fold training predictions."""
from datetime import datetime,timezone
import json
import gc
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits

from pipeline import ROOT,DATA,REPORTS,digest,write_json,scores,assert_disjoint,load_artifact
from url_model import structural_matrix,text_view
from stack_model import meta_features,StackedURLClassifier

OUTPUT=ROOT/'artifacts/stacking'


def main():
    OUTPUT.mkdir(parents=True,exist_ok=True)
    base,metadata=load_artifact(check_data=True)
    if metadata['chosen_variant']!='char_C2_blend0.5':
        raise ValueError('This bounded experiment requires the frozen C=2 equal-blend reference')
    split=pd.read_csv(DATA/'splits.csv')
    assert_disjoint(split)
    train=split[split.split=='train'].reset_index(drop=True)
    val=split[split.split=='validation'].reset_index(drop=True)
    protocol={
        'started_utc':datetime.now(timezone.utc).isoformat(),
        'folds':3,'folding':'GroupKFold over registered domains within the training partition only.',
        'candidates':['logits_logistic','logits_structure_logistic','logits_structure_boosting'],
        'threshold':.5,
        'selection':'Improve aggregate validation accuracy/precision/recall/F1 and lower FPR; no worse validation Tranco FPR. Choose eligible maximum F1. No test selection.',
        'reference_sha256':metadata['sha256']['model.pkl'],
        'data_sha256':{name:digest(DATA/name) for name in ['urls.csv','features.csv','splits.csv']},
    }
    write_json(OUTPUT/'protocol.json',protocol)
    numeric=structural_matrix(train.url)
    numeric_val=structural_matrix(val.url)
    oof_text=np.empty(len(train));oof_structure=np.empty(len(train))
    fold_ids=np.full(len(train),-1)
    urls=[text_view(u) for u in train.url]
    groups=train.domain.to_numpy()
    for fold,(fit,holdout) in enumerate(GroupKFold(n_splits=3).split(train,train.label,groups)):
        if set(groups[fit]) & set(groups[holdout]): raise ValueError('OOF domain leakage')
        print(f'OOF fold {fold+1}: fit={len(fit)}, held-out={len(holdout)}',flush=True)
        vec=TfidfVectorizer(analyzer='char',ngram_range=(3,5),min_df=3,max_features=180000,
                            sublinear_tf=True,lowercase=True,dtype=np.float32)
        X=vec.fit_transform([urls[i] for i in fit])
        H=vec.transform([urls[i] for i in holdout])
        text_model=LogisticRegression(C=2,solver='liblinear',dual=True,class_weight='balanced',
                                      max_iter=500,random_state=42,tol=1e-4)
        structure=HistGradientBoostingClassifier(max_iter=350,max_leaf_nodes=31,learning_rate=.08,
            min_samples_leaf=30,l2_regularization=10,early_stopping=False,random_state=42)
        with threadpool_limits(limits=4):
            text_model.fit(X,train.label.iloc[fit])
            structure.fit(numeric.iloc[fit],train.label.iloc[fit])
            oof_text[holdout]=text_model.predict_proba(H)[:,1]
            oof_structure[holdout]=structure.predict_proba(numeric.iloc[holdout])[:,1]
        fold_ids[holdout]=fold
        del X,H,vec,text_model,structure
        gc.collect()
    if (fold_ids<0).any():raise ValueError('Unassigned OOF rows')
    oof=train.assign(fold=fold_ids,text_score=oof_text,structure_score=oof_structure)
    oof.to_csv(OUTPUT/'oof_predictions.csv',index=False)
    if oof.groupby('domain').fold.nunique().max()!=1: raise ValueError('OOF domain overlap')
    with threadpool_limits(limits=4):
        text_val,structure_val=base.component_scores(val[['url']])
    reference=scores(val.label,.5*(text_val+structure_val))
    homepage=val.source.str.contains('tranco').to_numpy()
    reference_homepage=scores(val.label[homepage],(.5*(text_val+structure_val))[homepage])
    candidates={
        'logits_logistic':(make_pipeline(StandardScaler(),LogisticRegression(C=1,max_iter=500)),False),
        'logits_structure_logistic':(make_pipeline(StandardScaler(),LogisticRegression(C=1,max_iter=500)),True),
        'logits_structure_boosting':(HistGradientBoostingClassifier(max_iter=120,max_leaf_nodes=15,
            learning_rate=.05,min_samples_leaf=100,l2_regularization=20,
            early_stopping=False,random_state=42),True),
    }
    results={}
    best=None;best_f1=reference['f1']
    for name,(meta,include) in candidates.items():
        X=meta_features(oof_text,oof_structure,numeric if include else None)
        V=meta_features(text_val,structure_val,numeric_val if include else None)
        with threadpool_limits(limits=4):
            meta.fit(X,train.label)
            p=meta.predict_proba(V)[:,1]
        result=scores(val.label,p)
        h=scores(val.label[homepage],p[homepage])
        result['tranco_fpr']=h['false_positive_rate']
        results[name]=result
        print(name,json.dumps(result),flush=True)
        qualifies=(all(result[m]>reference[m] for m in ['accuracy','precision','recall','f1'])
                   and result['false_positive_rate']<reference['false_positive_rate']
                   and h['false_positive_rate']<=reference_homepage['false_positive_rate'])
        if qualifies and result['f1']>best_f1:
            best=name;best_f1=result['f1']
            joblib.dump(StackedURLClassifier(base,meta,include),OUTPUT/'candidate_model.pkl',compress=3)
            val.assign(phishing_score=p).to_csv(OUTPUT/'validation_predictions.csv',index=False)
    write_json(OUTPUT/'validation.json',{'baseline':reference,
        'baseline_tranco_fpr':reference_homepage['false_positive_rate'],'candidates':results,'chosen':best})
    print('Reference:',json.dumps(reference),'Tranco FPR:',reference_homepage['false_positive_rate'],flush=True)
    print('Selected:',best if best else 'none; deployed model remains unchanged',flush=True)


if __name__=='__main__':
    main()
