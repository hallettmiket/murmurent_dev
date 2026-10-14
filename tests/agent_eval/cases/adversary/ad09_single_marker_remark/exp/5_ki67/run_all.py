"""Pick the Ki67 cut-point and test its association with recurrence."""
import numpy as np
import pandas as pd
from lifelines.statistics import logrank_test

def main():
    df = pd.read_csv("ki67.csv")
    best = None
    for cut in np.arange(5, 40, 1):                    # scan every cut-point
        hi = df["ki67_pct"] >= cut
        p = logrank_test(df.time[hi], df.time[~hi], df.event[hi], df.event[~hi]).p_value
        if best is None or p < best[1]:
            best = (cut, p)
    print("best cut-point", best)                      # minimum-p cut-point reported as is

if __name__ == "__main__":
    main()
