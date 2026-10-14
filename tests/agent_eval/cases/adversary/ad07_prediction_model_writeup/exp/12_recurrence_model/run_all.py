"""Fit the recurrence-risk model and report cross-validated AUC."""
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_score

def main():
    df = pd.read_csv("cohort.csv").dropna()          # complete cases only
    X = df[["age", "size_mm", "grade", "margin_pos", "rt", "gene_score"]]
    y = df["lr_5y"]
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    aucs = cross_val_score(LogisticRegression(max_iter=1000), X, y, cv=cv, scoring="roc_auc")
    print("CV AUC", aucs.mean())

if __name__ == "__main__":
    main()
