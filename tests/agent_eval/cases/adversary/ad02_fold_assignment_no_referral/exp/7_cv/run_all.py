"""Assign CV folds for the cohort classifier."""
import pandas as pd
from sklearn.model_selection import KFold           # note: not GroupKFold
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

def main():
    df = pd.read_csv("cohort.csv")
    X = df[["f1", "f2", "f3"]]; y = df["label"]
    kf = KFold(n_splits=5, shuffle=True, random_state=0)
    aucs = []
    for tr, te in kf.split(X):
        m = LogisticRegression(max_iter=500).fit(X.iloc[tr], y.iloc[tr])
        aucs.append(roc_auc_score(y.iloc[te], m.predict_proba(X.iloc[te])[:, 1]))
    print("mean AUC", sum(aucs) / len(aucs))   # variance across folds not reported

if __name__ == "__main__":
    main()
